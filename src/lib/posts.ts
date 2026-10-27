import type { Post } from "../types/post";

/**
 * URL slug of a post: the `slug` frontmatter property, falling back to the
 * filename (sans extension) when none is set.
 */
export function getPostSlug(path: string, post: any): string {
  const filename = path.split("/").pop()!.replace(".mdx", "");
  return post.frontmatter.slug ?? filename;
}

/**
 * Process raw post files into Post objects. Posts live at the site root:
 * `/<slug>` (old `/posts/<slug>` links redirect there, see astro.config.mjs).
 */
export function processPosts(postFiles: Record<string, any>): Post[] {
  return Object.entries(postFiles).map(([path, post]: [string, any]) => ({
    url: `/${getPostSlug(path, post)}`,
    frontmatter: post.frontmatter,
  }));
}

/**
 * Sort posts by date in descending order (newest first)
 */
export function sortPostsByDate(
  posts: Post[],
  descending: boolean = true,
): Post[] {
  return [...posts].sort((a, b) => {
    const dateA = new Date(a.frontmatter.date).valueOf();
    const dateB = new Date(b.frontmatter.date).valueOf();
    return descending ? dateB - dateA : dateA - dateB;
  });
}

/**
 * Get unique categories from posts
 */
export function getUniqueCategories(
  posts: Post[],
  sort: boolean = true,
): string[] {
  const categories = [
    ...new Set(
      posts
        .map((post) => post.frontmatter.category)
        .filter(Boolean) as string[],
    ),
  ];
  return sort ? categories.sort() : categories;
}

/**
 * Get unique years from posts
 */
export function getUniqueYears(posts: Post[], sort: boolean = true): number[] {
  const years = [
    ...new Set(
      posts.map((post) => new Date(post.frontmatter.date).getFullYear()),
    ),
  ];
  return sort ? years.sort((a, b) => b - a) : years;
}

/**
 * Group posts by year
 */
export function groupPostsByYear(posts: Post[]): Record<number, Post[]> {
  return posts.reduce((acc: Record<number, Post[]>, post) => {
    const year = new Date(post.frontmatter.date).getFullYear();
    if (!acc[year]) {
      acc[year] = [];
    }
    acc[year].push(post);
    return acc;
  }, {});
}

/**
 * Filter posts by category (case-insensitive)
 */
export function filterPostsByCategory(posts: Post[], category: string): Post[] {
  return posts.filter(
    (post) =>
      post.frontmatter.category?.toLowerCase() === category.toLowerCase(),
  );
}

/**
 * Filter posts by year
 */
export function filterPostsByYear(
  posts: Post[],
  year: number | string,
): Post[] {
  const yearNumber = typeof year === "string" ? parseInt(year) : year;
  return posts.filter(
    (post) => new Date(post.frontmatter.date).getFullYear() === yearNumber,
  );
}
