import {
  ancestors,
  indexPeople,
  layoutHierarchy,
} from '../components/orgChart/hierarchy';
test('large flat forests lay out without recursive stack overflow or duplicate nodes', () => {
  const items = Array.from({ length: 5000 }, (_, i) => ({
    id: String(i),
    manager_id: i ? String(i - 1) : null,
    department_name: i === 4999 ? 'Target' : 'Other',
  }));
  const index = indexPeople({ items });
  for (const mode of ['tree', 'stacked']) {
    const layout = layoutHierarchy(index, new Set(), {}, mode);
    expect(layout.positions.size).toBe(5000);
  }
  expect(ancestors('4999', index.people)).toHaveLength(4999);
});
test('filters retain ancestors and collapsed counts remain authoritative', () => {
  const index = indexPeople({
    items: [
      { id: 'a', department_name: 'A' },
      { id: 'b', manager_id: 'a', department_name: 'B' },
    ],
  });
  expect(
    layoutHierarchy(index, new Set(['a']), {}, 'tree').positions.size,
  ).toBe(1);
  const filtered = layoutHierarchy(
    index,
    new Set(['a']),
    { department_name: 'B' },
    'tree',
  );
  expect(filtered.matching.size).toBe(1);
  expect(filtered.positions.size).toBe(2);
});
