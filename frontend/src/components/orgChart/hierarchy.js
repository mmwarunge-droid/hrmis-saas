export const CARD_WIDTH = 256;
export const CARD_HEIGHT = 174;
const GAP = 28;

export function indexPeople(data) {
  const items = data.items || [];
  if (!data.items) {
    const stack = (data.roots || []).map((p) => ({ ...p, manager_id: null }));
    while (stack.length) {
      const person = stack.pop();
      items.push(person);
      stack.push(
        ...(person.children || []).map((p) => ({
          ...p,
          manager_id: person.id,
        })),
      );
    }
  }
  const people = new Map(items.map((p) => [p.id, { ...p, children: [] }]));
  const roots = [];
  for (const person of people.values()) {
    const parent = people.get(person.manager_id);
    if (parent && parent !== person) parent.children.push(person.id);
    else roots.push(person.id);
  }
  return { people, roots };
}

export function ancestors(id, people) {
  const result = [],
    seen = new Set([id]);
  let parent = people.get(id)?.manager_id;
  while (parent && people.has(parent) && !seen.has(parent)) {
    result.push(parent);
    seen.add(parent);
    parent = people.get(parent).manager_id;
  }
  return result;
}

export function matches(person, filters) {
  return Object.entries(filters).every(
    ([key, value]) => !value || person[key] === value,
  );
}

export function layoutHierarchy(index, collapsed, filters, mode) {
  const { people, roots } = index;
  const matching = new Set(
    [...people.values()].filter((p) => matches(p, filters)).map((p) => p.id),
  );
  const included = new Set(matching);
  for (const id of matching) {
    let parent = people.get(id)?.manager_id;
    while (parent && people.has(parent) && !included.has(parent)) {
      included.add(parent);
      parent = people.get(parent).manager_id;
    }
  }
  const filtering = Object.values(filters).some(Boolean);
  const order = [],
    seen = new Set(),
    children = new Map();
  const stack = roots
    .slice()
    .reverse()
    .map((id) => ({ id, depth: 0, parent: null }));
  while (stack.length) {
    const entry = stack.pop();
    if (seen.has(entry.id) || !included.has(entry.id)) continue;
    seen.add(entry.id);
    order.push(entry);
    const ids =
      !filtering && collapsed.has(entry.id)
        ? []
        : people.get(entry.id).children.filter((id) => included.has(id));
    children.set(entry.id, ids);
    for (const id of ids.slice().reverse())
      stack.push({ id, depth: entry.depth + 1, parent: entry.id });
  }
  const positions = new Map();
  if (mode === 'stacked') {
    order.forEach((entry, i) =>
      positions.set(entry.id, {
        ...entry,
        x: entry.depth * 56,
        y: i * (CARD_HEIGHT + GAP),
      }),
    );
  } else {
    const widths = new Map();
    for (const entry of order.slice().reverse()) {
      widths.set(
        entry.id,
        Math.max(
          CARD_WIDTH + GAP,
          (children.get(entry.id) || []).reduce(
            (sum, id) => sum + (widths.get(id) || 0),
            0,
          ),
        ),
      );
    }
    let rootX = 0;
    const pending = [];
    for (const id of roots.filter((key) => seen.has(key))) {
      pending.push({ id, left: rootX });
      rootX += widths.get(id);
    }
    const entries = new Map(order.map((e) => [e.id, e]));
    while (pending.length) {
      const { id, left } = pending.pop();
      const entry = entries.get(id);
      positions.set(id, {
        ...entry,
        x: left + (widths.get(id) - CARD_WIDTH) / 2,
        y: entry.depth * (CARD_HEIGHT + 64),
      });
      let x = left;
      for (const child of children.get(id) || []) {
        pending.push({ id: child, left: x });
        x += widths.get(child);
      }
    }
  }
  let width = CARD_WIDTH,
    height = CARD_HEIGHT;
  for (const p of positions.values()) {
    width = Math.max(width, p.x + CARD_WIDTH);
    height = Math.max(height, p.y + CARD_HEIGHT);
  }
  return { positions, width: width + 48, height: height + 48, matching };
}

const COLORS = [
  '#2563eb',
  '#7c3aed',
  '#0f766e',
  '#b45309',
  '#be185d',
  '#475569',
];
export function categoryColor(value) {
  let hash = 0;
  for (const char of value || '') hash = (hash * 31 + char.charCodeAt(0)) | 0;
  return COLORS[Math.abs(hash) % COLORS.length];
}
