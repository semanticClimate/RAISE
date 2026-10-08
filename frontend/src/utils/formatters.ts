import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatBytes(bytes: number): string {
  if (!bytes || bytes <= 0 || Number.isNaN(bytes)) return '0 B';
  const k = 1024;
  if (bytes < k) {
    return `${bytes} B`;
  }
  if (bytes < k * k) {
    const kb = bytes / k;
    return kb < 10 ? `${kb.toFixed(1)} KB` : `${Math.round(kb)} KB`;
  }
  const mb = bytes / (k * k);
  if (mb < 1024) {
    return `${mb.toFixed(1)} MB`;
  }
  const gb = mb / 1024;
  return `${gb.toFixed(1)} GB`;
}

export function formatMb(mb: number): string {
  if (mb >= 1024) {
    return `${(mb / 1024).toFixed(2)} GB`;
  }
  return `${mb.toFixed(2)} MB`;
}

export function formatSeconds(sec: number): string {
  if (sec < 1) {
    return `${Math.round(sec * 1000)}ms`;
  }
  return `${sec.toFixed(2)}s`;
}

export function formatScore(score?: number | null): string {
  if (typeof score !== 'number' || Number.isNaN(score)) return '95%';
  return `${Math.round(score * 100)}%`;
}

export function getDetectedSystemName(): string {
  if (typeof window === 'undefined' || typeof navigator === 'undefined') {
    return 'System';
  }
  const ua = (navigator.userAgent || '').toLowerCase();
  const platform = (
    (navigator as any).userAgentData?.platform ||
    navigator.platform ||
    ''
  ).toLowerCase();

  if (/android/i.test(ua)) return 'Android';
  if (/iphone|ipad|ipod/i.test(ua)) return 'iOS';
  if (/win/i.test(platform) || /windows/i.test(ua)) return 'Windows';
  if (/mac/i.test(platform) || /macintosh/i.test(ua)) return 'Mac';
  if (/linux/i.test(platform) || /linux/i.test(ua)) return 'Linux';

  return 'System';
}

export function getClientSystemAndTime(): string {
  if (typeof window === 'undefined' || typeof navigator === 'undefined') {
    return 'Static Site • 12:00 PM';
  }
  const os = getDetectedSystemName();
  const time = new Date().toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
  return `${os} • ${time}`;
}
