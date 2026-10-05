export function pageWindow(page: number, pageCount: number): number[] {
  return Array.from({ length: pageCount }, (_, index) => index + 1).filter(
    value => value === 1 || value === pageCount || Math.abs(value - page) <= 1,
  )
}
