import { z } from 'zod';
import { GraphEdgeSchema, GraphNodeSchema } from './chat';

export const FullGraphResponseSchema = z.preprocess(
  (val: any) => {
    if (val && typeof val === 'object') {
      return {
        ...val,
        total_nodes:
          val.total_nodes ?? val.node_count ?? (Array.isArray(val.nodes) ? val.nodes.length : 0),
        total_edges:
          val.total_edges ?? val.edge_count ?? (Array.isArray(val.edges) ? val.edges.length : 0),
      };
    }
    return val;
  },
  z.object({
    nodes: z.array(GraphNodeSchema).default([]),
    edges: z.array(GraphEdgeSchema).default([]),
    total_nodes: z.number().int().optional(),
    total_edges: z.number().int().optional(),
  })
);

export type FullGraphResponse = z.infer<typeof FullGraphResponseSchema>;

export const SearchRequestSchema = z.object({
  query: z.string().min(1, 'Search query cannot be empty'),
  limit: z.number().int().min(1).max(20).default(5),
  top_k: z.number().int().min(1).max(20).optional(),
});

export type SearchRequest = z.infer<typeof SearchRequestSchema>;

export const SearchResultItemSchema = z.preprocess(
  (val: any) => {
    if (val && typeof val === 'object') {
      return {
        ...val,
        chunk_id: val.chunk_id || val.id || '',
        text: val.text || val.plain_text || val.content || '',
      };
    }
    return val;
  },
  z.object({
    chunk_id: z.string(),
    text: z.string(),
    similarity: z.number().default(0),
    metadata: z.record(z.string(), z.any()).default({}),
  })
);

export type SearchResultItem = z.infer<typeof SearchResultItemSchema>;

export const SearchResponseSchema = z.array(SearchResultItemSchema).or(
  z.object({
    results: z.array(SearchResultItemSchema).default([]),
  })
);

export type SearchResponse = z.infer<typeof SearchResponseSchema>;
