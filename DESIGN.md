---
# Design tokens for this product (impeccable-style DESIGN.md, light)
mode: operate
dials:
  design_variance: 5
  motion_intensity: 3
  visual_density: 5
---

# 商品图片工作台 · Design

## 1. Aesthetic direction

Quiet workshop tool for e-commerce operators. Warm paper surfaces, ink type,
one muted workshop-blue accent. Images are the hero; chrome stays quiet.
**Not** a marketing landing page (no gradient heroes, no equal feature cards).

## 2. Color

| Role | Value |
|------|-------|
| Page | `#f3f1ec` |
| Surface | `#fdfcfa` |
| Raised | `#ffffff` |
| Ink primary | `#1c1917` |
| Ink secondary | `#57534e` |
| Muted | `#a8a29e` |
| Accent | `#3d5a80` |
| Accent soft | `#e8eef5` |
| Danger | `#b42318` |
| Success | `#276749` |
| Warning | `#b45309` |

## 3. Typography

- Family: Inter / PingFang SC / Microsoft YaHei
- Scale: 11.5 / 13 / 14.5 / 16 / 18 / 22
- Headings: weight 600, tracking `-0.02em`
- Body line-height ≈ 1.55–1.65

## 4. Layout

- Sidebar 212px (collapsed 52px) + fluid content
- Card grid: 1→2→3→4 columns, gap 12px
- 4px spacing base

## 5. Principles

1. Hierarchy via surface + type weight, not shadow stacks
2. Folder cards more present than product cards (navigation vs content)
3. Empty states are next actions, never mood pieces
4. Motion only answers user actions; honor `prefers-reduced-motion`
5. Avoid AI tells: cream+terracotta, purple mesh, ALL-CAPS eyebrows,
   middle-dot meta, arrow CTAs, identical card kit

## 6. Do / Don't

**Do** ink primary buttons · whisper borders · sentence-case Chinese copy ·
focus-visible rings · tabular numbers for counts/dates

**Don't** big brand-blue slabs · gradient decoration · emoji in chrome ·
apologetic error copy · dense motion on load
