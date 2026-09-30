export const MOCK_FOLDERS = [
  { id: 'f1', name: '摩托车配件', createdAt: '2026-09-20 10:00' },
  { id: 'f2', name: '数码周边', createdAt: '2026-09-21 09:00' },
  { id: 'f3', name: '汽车用品', createdAt: '2026-09-22 14:00' },
  { id: 'f4', name: '待整理', createdAt: '2026-09-23 08:00' },
]

export const MOCK_PRODUCTS = [
  {
    id: 'p1',
    folderId: 'f1',
    name: '摩托车高亮辅助灯',
    market: '北美',
    facts: '12V 电压，防水等级 IP67，铝合金外壳。',
    updatedAt: '2026-09-28 10:00',
  },
  {
    id: 'p2',
    folderId: 'f2',
    name: 'USB-C 10合1扩展坞',
    market: '欧洲',
    facts: '支持 4K@60Hz，PD 100W 充电。',
    updatedAt: '2026-09-28 09:30',
  },
  {
    id: 'p3',
    folderId: 'f3',
    name: '汽车内饰清洁软胶',
    market: '东南亚',
    facts: '无毒环保材料，不留残胶。',
    updatedAt: '2026-09-27 15:20',
  },
]

const placeholder = (seed, text) =>
  `https://placehold.co/400x400/e5e7eb/6b7280?text=${encodeURIComponent(text || seed)}`

export const MOCK_REFERENCES = {
  p1: [
    {
      id: 'r1',
      assetId: 'a1',
      url: placeholder('ref1', 'Ref 1'),
      source: 'same',
      purposes: ['overall', 'detail'],
      desc: '主要参考外壳金属质感',
      status: 'success',
    },
    {
      id: 'r2',
      assetId: 'a2',
      url: placeholder('ref2', 'Ref 2'),
      source: 'other',
      purposes: ['install'],
      desc: '参考支架安装方式，不要参考灯泡形状',
      status: 'success',
    },
  ],
  p2: [],
  p3: [
    {
      id: 'r3',
      assetId: 'a3',
      url: placeholder('ref3', 'Ref 3'),
      source: 'ai',
      purposes: ['composition'],
      desc: '',
      status: 'success',
    },
    {
      id: 'r4',
      assetId: 'a4',
      url: placeholder('ref4', 'Ref 4'),
      source: '',
      purposes: [],
      desc: '',
      status: 'success',
    },
  ],
}
