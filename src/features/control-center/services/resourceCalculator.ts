import type { ControlCenterConfig } from '../types';

export interface AddedSubstrate {
  category: 'Platform' | 'Inference' | 'Knowledge Graph' | 'Storage' | 'Cache';
  label: string;
  diskGb: number;
  ramGb: number;
  isCloud: boolean;
}

export interface ResourceFootprint {
  totalDiskGb: number;
  totalRamGb: number;
  estimatedTime: string;
  addedSubstrates: AddedSubstrate[];
}

export const calculateResourceFootprint = (config: ControlCenterConfig): ResourceFootprint => {
  let totalDiskGb = 0;
  let totalRamGb = 1.2; // Base RAISE system memory footprint
  const addedSubstrates: AddedSubstrate[] = [];

  // 1. Platform substrate
  addedSubstrates.push({
    category: 'Platform',
    label: config.targetPlatform.toUpperCase(),
    diskGb: 0,
    ramGb: 0,
    isCloud: false,
  });

  // 2. Intelligence Engine (Cloud vs Local)
  const isCloudLlm = config.llmDeployment
    ? config.llmDeployment === 'cloud'
    : !config.llmMode || config.llmMode.startsWith('cloud');

  if (isCloudLlm) {
    const validKeys = (config.apiKeys || []).filter((k) => k?.key && k.key.trim().length > 0);
    const providers =
      Array.from(new Set(validKeys.map((k) => k.providerName))).join(', ') || 'Cloud Inference';
    addedSubstrates.push({
      category: 'Inference',
      label: `Cloud API (${providers})`,
      diskGb: 0,
      ramGb: 0,
      isCloud: true,
    });
  } else {
    // Dynamic parameter parser for model size and memory requirements (zero hardcoding)
    const modelStr = (config.selectedLocalModel || '').toLowerCase();
    let disk = 0;
    let ram = 0;
    if (modelStr) {
      disk = 2.0;
      ram = 4.0;
      const paramMatch = modelStr.match(/(\d+(?:\.\d+)?)[bB]/);
      if (paramMatch) {
        const paramVal = parseFloat(paramMatch[1]);
        if (paramVal <= 3.5) {
          disk = Math.round(paramVal * 0.7 * 10) / 10;
          ram = 4.0;
        } else if (paramVal <= 9.0) {
          disk = Math.round(paramVal * 0.65 * 10) / 10;
          ram = 8.0;
        } else if (paramVal <= 16.0) {
          disk = Math.round(paramVal * 0.6 * 10) / 10;
          ram = 16.0;
        } else {
          disk = Math.round(paramVal * 0.55 * 10) / 10;
          ram = 32.0;
        }
      }
    }
    const displayName = config.selectedLocalModel
      ? config.selectedLocalModel.split('/').pop()?.replace(/[-_]/g, ' ') || config.selectedLocalModel
      : 'Local Inference Engine';

    totalDiskGb += disk;
    totalRamGb += ram;
    addedSubstrates.push({
      category: 'Inference',
      label: displayName,
      diskGb: disk,
      ramGb: ram,
      isCloud: false,
    });
  }

  // 3. Knowledge Graph Substrate (Neo4j)
  if (config.neo4jMode === 'local') {
    totalDiskGb += 1.5;
    totalRamGb += 0.5;
    addedSubstrates.push({
      category: 'Knowledge Graph',
      label: 'Local Neo4j Bolt',
      diskGb: 1.5,
      ramGb: 0.5,
      isCloud: false,
    });
  } else if (config.neo4jMode === 'cloud') {
    addedSubstrates.push({
      category: 'Knowledge Graph',
      label: 'Neo4j AuraDB Cloud',
      diskGb: 0,
      ramGb: 0,
      isCloud: true,
    });
  } else {
    addedSubstrates.push({
      category: 'Knowledge Graph',
      label: 'Vector Search Fallback',
      diskGb: 0,
      ramGb: 0,
      isCloud: false,
    });
  }

  // 4. Persistence & Cache Substrates
  if (config.postgresMode === 'cloud') {
    addedSubstrates.push({
      category: 'Storage',
      label: 'Cloud Neon Postgres',
      diskGb: 0,
      ramGb: 0,
      isCloud: true,
    });
  } else {
    addedSubstrates.push({
      category: 'Storage',
      label: 'In-Memory Sessions',
      diskGb: 0,
      ramGb: 0,
      isCloud: false,
    });
  }

  if (config.redisMode === 'cloud') {
    addedSubstrates.push({
      category: 'Cache',
      label: 'Cloud Upstash Redis',
      diskGb: 0,
      ramGb: 0,
      isCloud: true,
    });
  } else {
    addedSubstrates.push({
      category: 'Cache',
      label: 'In-Memory Cache',
      diskGb: 0,
      ramGb: 0,
      isCloud: false,
    });
  }

  // Estimated Setup Time calculation
  let estimatedTime = 'Instant (~15 seconds)';
  if (totalDiskGb >= 4.0) {
    estimatedTime = '~3 – 5 min download';
  } else if (totalDiskGb > 0) {
    estimatedTime = '~1 – 2 min download';
  }

  return {
    totalDiskGb: Math.round(totalDiskGb * 10) / 10,
    totalRamGb: Math.round(totalRamGb * 10) / 10,
    estimatedTime,
    addedSubstrates,
  };
};
