/**
 * Graph Layout - 图布局算法
 */

export function calculateNodePosition(agent: any): { x: number; y: number } {
  // 简单的树形布局
  const depth = agent.depth || 0;
  const baseY = 100 + depth * 200;

  // 根据角色分配 x 位置
  const roleHash = agent.role.split('').reduce((acc: number, char: string) => acc + char.charCodeAt(0), 0);
  const baseX = 100 + (roleHash % 800);

  return { x: baseX, y: baseY };
}

export function calculateLayout(agents: Record<string, any>): {
  nodes: any[];
  edges: any[];
} {
  const nodes = Object.values(agents).map((agent) => ({
    id: agent.node_id,
    type: 'agentNode',
    position: calculateNodePosition(agent),
    data: agent,
  }));

  const edges: any[] = [];

  Object.values(agents).forEach((agent) => {
    if (agent.parent_id && agents[agent.parent_id]) {
      edges.push({
        id: `${agent.parent_id}-${agent.node_id}`,
        source: agent.parent_id,
        target: agent.node_id,
      });
    }
  });

  return { nodes, edges };
}
