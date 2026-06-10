export interface PostFrontmatter {
  title: string;
  date: string;
  /** Optional URL slug override; defaults to the filename when omitted */
  slug?: string;
  category?: string;
  description?: string;
  externalUrl?: string;
  embedType?: "youtube" | "strava" | "instagram" | "alltrails";
  embedId?: string;
}

export interface Post {
  url: string;
  frontmatter: PostFrontmatter;
}
