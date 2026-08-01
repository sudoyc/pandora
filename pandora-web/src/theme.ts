export const THEMES = [
  { id: 'forest', label: 'Forest' },
  { id: 'signal', label: 'Signal' },
  { id: 'marine', label: 'Marine' },
] as const;

export type ThemeName = (typeof THEMES)[number]['id'];

export function isThemeName(value: string | null): value is ThemeName {
  return THEMES.some((theme) => theme.id === value);
}
