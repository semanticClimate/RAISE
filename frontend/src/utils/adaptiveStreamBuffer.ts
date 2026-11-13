/**
 * Sub-60fps Adaptive Token Stream Buffer
 * =====================================
 * Dynamically adjusts React state reconciliation intervals during massive
 * 100+ tokens/sec LLM bursts to guarantee zero frame drops on lower-spec client GPUs.
 *
 * Algorithm:
 *  1. Low throughput (<150 chars/sec / ~35 tok/s):
 *     Flushes at native 60 FPS (~16ms) for immediate fluid rendering.
 *  2. High throughput burst (150-400 chars/sec / ~40-100 tok/s):
 *     Adapts flush window to ~28ms (~35 FPS) to eliminate micro-stutter.
 *  3. Extreme burst (>400 chars/sec / >100 tok/s):
 *     Adapts flush window to ~45ms (~22 FPS) to give the client browser plenty of
 *     idle time for KaTeX/Markdown DOM layout and GPU compositing.
 *  4. Document Length Scaling:
 *     Sets minimum interval floor based on accumulated document length (30ms for >2.5k, 45ms for >6k)
 *     so large documents don't starve the UI thread even at low velocities.
 *  5. Real Post-Paint Frame Contention Backoff:
 *     Measures post-paint frame time with requestAnimationFrame. If paint delta exceeds 24ms,
 *     the buffer automatically increases the interval by +8ms (up to maxIntervalMs).
 *  6. Efficient Sleep Schedule:
 *     Replaces busy-wait requestAnimationFrame loop with targeted setTimeout sleeping.
 *  7. Immediate Terminal Flush:
 *     `flushImmediately()` synchronously delivers the exact accumulated text with 0ms lag
 *     the instant the stream finishes or stops.
 */

export interface AdaptiveBufferOptions {
  minIntervalMs?: number; // default: 16ms (60 FPS)
  maxIntervalMs?: number; // default: 45ms (~22 FPS)
  onFlush: (accumulatedText: string) => void;
}

export class AdaptiveStreamBuffer {
  private readonly minIntervalMs: number;
  private readonly maxIntervalMs: number;
  private readonly onFlush: (accumulatedText: string) => void;

  private latestText: string = '';
  private lastFlushedText: string = '';
  private lastFlushTime: number = 0;
  private rafId: number | null = null;
  private timeoutId: ReturnType<typeof setTimeout> | null = null;

  // Throughput velocity tracking
  private recentSamples: Array<{ timestamp: number; charCount: number }> = [];
  private currentIntervalMs: number;
  private isDestroyed: boolean = false;

  constructor(options: AdaptiveBufferOptions) {
    this.minIntervalMs = options.minIntervalMs ?? 16;
    this.maxIntervalMs = options.maxIntervalMs ?? 45;
    this.currentIntervalMs = this.minIntervalMs;
    this.onFlush = options.onFlush;
  }

  private getNow(): number {
    if (typeof performance !== 'undefined' && typeof performance.now === 'function') {
      return performance.now();
    }
    return Date.now();
  }

  /**
   * Ingests a new accumulated stream payload from the SSE reader.
   * Calculates velocity, factors in document length, and schedules an adaptive frame flush.
   */
  public push(accumulatedText: string): void {
    if (this.isDestroyed) return;
    const now = this.getNow();
    this.latestText = accumulatedText;

    // Track throughput velocity within a sliding 500ms window
    this.recentSamples.push({ timestamp: now, charCount: accumulatedText.length });
    const cutoff = now - 500;
    while (this.recentSamples.length > 1 && this.recentSamples[0].timestamp < cutoff) {
      this.recentSamples.shift();
    }

    let velocityIntervalMs = this.minIntervalMs;
    if (this.recentSamples.length >= 2) {
      const oldest = this.recentSamples[0];
      const deltaMs = Math.max(10, now - oldest.timestamp);
      const deltaChars = Math.max(0, accumulatedText.length - oldest.charCount);
      const charsPerSec = (deltaChars / deltaMs) * 1000;

      if (charsPerSec > 400) {
        // Extreme burst (>100 tok/s): smooth at ~22 FPS to prevent layout thrashing
        velocityIntervalMs = this.maxIntervalMs;
      } else if (charsPerSec > 150) {
        // High burst (~40-90 tok/s): smooth at ~35 FPS
        velocityIntervalMs = Math.round(
          this.minIntervalMs + (this.maxIntervalMs - this.minIntervalMs) * 0.5
        );
      } else {
        // Normal pace (<35 tok/s): standard 60 FPS
        velocityIntervalMs = this.minIntervalMs;
      }
    }

    // Scale flush interval by document length
    let lengthFloorMs = this.minIntervalMs;
    if (accumulatedText.length > 6000) {
      lengthFloorMs = 45;
    } else if (accumulatedText.length > 2500) {
      lengthFloorMs = 30;
    }

    this.currentIntervalMs = Math.min(
      this.maxIntervalMs,
      Math.max(velocityIntervalMs, lengthFloorMs)
    );

    this.scheduleFrame(now);
  }

  private scheduleFrame(now: number): void {
    if (this.rafId !== null || this.timeoutId !== null) return;

    const timeSinceLastFlush = now - this.lastFlushTime;
    const remainingDelay = Math.max(0, this.currentIntervalMs - timeSinceLastFlush);

    const executeFlush = () => {
      this.rafId = null;
      this.timeoutId = null;
      if (this.isDestroyed) return;

      const frameStart = this.getNow();
      if (this.latestText !== this.lastFlushedText) {
        this.lastFlushedText = this.latestText;
        this.lastFlushTime = frameStart;
        this.onFlush(this.latestText);

        // Measure real post-paint frame time instead of synchronous setState call
        if (typeof requestAnimationFrame !== 'undefined') {
          requestAnimationFrame(() => {
            if (this.isDestroyed) return;
            const paintDelta = this.getNow() - frameStart;
            if (paintDelta > 24) {
              // Frame dropped / UI thread contention: back off interval
              this.currentIntervalMs = Math.min(this.maxIntervalMs, this.currentIntervalMs + 8);
            }
          });
        }
      }

      // If more text accumulated while flushing, reschedule for next cycle
      if (this.latestText !== this.lastFlushedText) {
        this.scheduleFrame(this.getNow());
      }
    };

    if (remainingDelay <= 4) {
      if (typeof requestAnimationFrame !== 'undefined') {
        this.rafId = requestAnimationFrame(executeFlush);
      } else {
        this.timeoutId = setTimeout(executeFlush, 0);
      }
    } else if (remainingDelay > 16) {
      // Avoid spinning requestAnimationFrame every 16ms when waiting
      this.timeoutId = setTimeout(() => {
        this.timeoutId = null;
        if (typeof requestAnimationFrame !== 'undefined') {
          this.rafId = requestAnimationFrame(executeFlush);
        } else {
          executeFlush();
        }
      }, remainingDelay - 8);
    } else {
      if (typeof requestAnimationFrame !== 'undefined') {
        this.rafId = requestAnimationFrame(executeFlush);
      } else {
        this.timeoutId = setTimeout(executeFlush, remainingDelay);
      }
    }
  }

  /**
   * Synchronously cancels pending frames and delivers the latest text immediately.
   */
  public flushImmediately(): void {
    if (this.rafId !== null && typeof cancelAnimationFrame !== 'undefined') {
      cancelAnimationFrame(this.rafId);
      this.rafId = null;
    }
    if (this.timeoutId !== null) {
      clearTimeout(this.timeoutId);
      this.timeoutId = null;
    }
    if (this.latestText !== this.lastFlushedText) {
      this.lastFlushedText = this.latestText;
      this.lastFlushTime = this.getNow();
      this.onFlush(this.latestText);
    }
  }

  /**
   * Resets internal state between chat queries.
   */
  public reset(): void {
    if (this.rafId !== null && typeof cancelAnimationFrame !== 'undefined') {
      cancelAnimationFrame(this.rafId);
      this.rafId = null;
    }
    if (this.timeoutId !== null) {
      clearTimeout(this.timeoutId);
      this.timeoutId = null;
    }
    this.latestText = '';
    this.lastFlushedText = '';
    this.lastFlushTime = 0;
    this.recentSamples = [];
    this.currentIntervalMs = this.minIntervalMs;
  }

  /**
   * Cleans up all pending timers and prevents future callbacks.
   */
  public destroy(): void {
    this.isDestroyed = true;
    if (this.rafId !== null && typeof cancelAnimationFrame !== 'undefined') {
      cancelAnimationFrame(this.rafId);
      this.rafId = null;
    }
    if (this.timeoutId !== null) {
      clearTimeout(this.timeoutId);
      this.timeoutId = null;
    }
  }

  public getCurrentIntervalMs(): number {
    return this.currentIntervalMs;
  }

  public getLatestText(): string {
    return this.latestText;
  }
}
