# My Minimal Blog

A minimal static blog built with Astro and MDX, inspired by the Hey WordPress theme, and hosted on GitHub Pages.

## Features

- 📝 Write posts in MDX (Markdown + JSX)
- 🎨 Clean, minimal design inspired by the Hey WordPress theme
- 🚀 Static site generation with Astro
- 📦 Zero JavaScript by default
- 🌐 Deployed to GitHub Pages

## Local Development

```bash
# Install dependencies
npm install

# Start dev server
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

## Formatting

Code is formatted with [Prettier](https://prettier.io/) (plus `prettier-plugin-astro` for `.astro` files).

```bash
# Format every file in place
npm run format

# Check formatting without writing (CI-friendly)
npm run format:check
```

## Deployment to GitHub Pages

1. **Create a GitHub repository** for your blog

2. **Update `astro.config.mjs`**:

   ```js
   export default defineConfig({
     site: "https://yourusername.github.io",
     base: "/your-repo-name", // Remove this line if using yourusername.github.io
     integrations: [mdx()],
   });
   ```

3. **Initialize git and push**:

   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git branch -M main
   git remote add origin https://github.com/yourusername/your-repo-name.git
   git push -u origin main
   ```

4. **Enable GitHub Pages**:
   - Go to your repository settings
   - Navigate to "Pages" in the sidebar
   - Under "Build and deployment", select "GitHub Actions" as the source
   - The workflow will automatically deploy on push to main

## Adding New Posts

Create a new `.mdx` file in `src/posts/`:

```mdx
---
title: "Your Post Title"
date: "2024-01-15"
category: "Thoughts"
slug: "your-post" # optional, defaults to the filename
---

Your post content here...
```

The post is served at `/<slug>` (for example `designcode.me/your-post`). Category pages
live at the same level (`/thoughts`, `/guides`, ...), so a slug must not equal a category
name; the build fails with a clear message if it does. Old `/posts/<slug>` links redirect to
the new address via the `"/posts/[slug]"` entry in `astro.config.mjs`.

### ⚠️ Gotcha: blank lines inside MDX expressions

Prettier formats the JavaScript inside an MDX `{…}` expression (e.g. a component's
`items={[…]}` prop) **only if it can parse the whole expression as one unit**. A blank
line _inside_ the `{…}` container breaks MDX's parse boundary, so Prettier silently gives
up and leaves the entire expression unformatted — and `npm run format:check` won't flag it,
because an unparseable expression reads as "already formatted."

```mdx
<Timeline
  items={[
    { title: "Day 1", embeds: [] },
                                    👈 a blank line here breaks formatting of the whole prop
    { title: "Day 2", embeds: [] },
  ]}
/>
```

Blank lines _between_ separate JSX elements are fine — just keep them out of `{…}`
expressions. If a `.mdx` file looks "stuck" and won't reformat, look for a stray blank line
(or a real syntax error) inside an embedded expression.

## Migrating posts from abbyontravel.com

Posts from the old WordPress.com blog are moved over one at a time with
`scripts/migrate-abbyontravel.py` (Python 3.9+, standard library only, no WordPress login
needed):

```bash
# dry run: print the MDX, download nothing, touch nothing
python3 scripts/migrate-abbyontravel.py https://abbyontravel.com/2019/10/29/1-day-hike-on-matterhorn-trail/ --dry-run

# for real: short slug + category of your choice
python3 scripts/migrate-abbyontravel.py https://abbyontravel.com/2019/10/29/1-day-hike-on-matterhorn-trail/ \
  --slug matterhorn-trail --category Guides
```

The script accepts a full URL, the WordPress slug, or the numeric post ID (travel-diary
_pages_ such as `/travels/a-hike-around-lake-como/` work too). For each post it:

1. fetches the content through the public WordPress.com REST API;
2. downloads every image into `public/<slug>/1.jpg, 2.jpg, ...` (WordPress resizes them to
   `--max-width` px on the long side, default 2048, and strips EXIF; use `--max-width 0`
   for untouched originals);
3. converts the WordPress blocks to MDX: galleries become `<PhotoGallery>`, single images
   become `<figure>` with a caption, YouTube embeds become `<EmbedYoutube>`, Google Maps
   embeds become `<EmbedGoogleMap>`;
4. writes `src/posts/<date>-<slug>.mdx` with `slug`, `title`, `date` and `category`
   frontmatter;
5. adds a redirect from the old path (e.g. `/2019/10/29/1-day-hike-on-matterhorn-trail`) to
   `/<slug>` in `astro.config.mjs` and runs Prettier on the touched files.

Review the generated MDX, run `npm run build`, and commit the post, its images and the
config change together. If the post already exists here (same title, or an
`externalUrl` stub pointing at abbyontravel.com) the script warns; re-run with
`--slug <existing-slug> --force` to replace the stub.

### Redirecting abbyontravel.com to designcode.me

Two layers make old links land on the right post:

- **Per post (this repo):** the `redirects` map in `astro.config.mjs` turns the old WordPress
  path into `/<slug>`. Astro emits a small HTML page with an instant
  `<meta http-equiv="refresh">` for each entry (GitHub Pages cannot send real 301s), so
  `designcode.me/2019/10/29/1-day-hike-on-matterhorn-trail/` already works as soon as the
  post is deployed.
- **Domain level (once the posts you want are migrated):** send every `abbyontravel.com`
  URL to the same path on `designcode.me` with a true 301. The free way is to move the
  domain's DNS to Cloudflare, proxy the apex record, and add one Single Redirect rule
  (Request URL `http*://abbyontravel.com/*` → Target `https://designcode.me/${2}`, 301,
  preserve query string). The Astro redirects above then finish the job per post.

## Customization

### Update Site Title

Edit the navigation link in `src/layouts/BaseLayout.astro:92`

### Change Colors

Modify CSS variables in `src/layouts/BaseLayout.astro:24-29`:

- `--color-primary`: Main text color
- `--color-secondary`: Secondary text color
- `--color-tertiary`: Borders and accents
- `--color-background`: Background color

### Add Custom Fonts

Add a `<link>` tag in the `<head>` section of `BaseLayout.astro` and update the `font-family` in the body styles.

## Project Structure

```
/
├── .github/workflows/
│   └── deploy.yml          # GitHub Actions deployment workflow
├── public/
│   └── favicon.svg
├── src/
│   ├── layouts/
│   │   ├── BaseLayout.astro    # Main layout with styling
│   │   └── PostLayout.astro    # Blog post layout
│   ├── pages/
│   │   ├── index.astro         # Homepage (blog list)
│   │   ├── [slug].astro        # A post, or a category listing
│   │   └── archive/            # Posts by year
│   └── posts/
│       ├── first-post.mdx
│       └── second-post.mdx
├── astro.config.mjs        # Astro configuration
└── package.json
```

## License

MIT
