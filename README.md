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

## Deployment to GitHub Pages

1. **Create a GitHub repository** for your blog

2. **Update `astro.config.mjs`**:
   ```js
   export default defineConfig({
     site: 'https://yourusername.github.io',
     base: '/your-repo-name', // Remove this line if using yourusername.github.io
     integrations: [mdx()]
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

Create a new `.mdx` file in `src/pages/posts/`:

```mdx
---
layout: ../../layouts/PostLayout.astro
title: 'Your Post Title'
date: '2024-01-15'
description: 'A brief description of your post'
---

Your post content here...
```

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
│   └── pages/
│       ├── index.astro         # Homepage (blog list)
│       └── posts/
│           ├── first-post.mdx
│           └── second-post.mdx
├── astro.config.mjs        # Astro configuration
└── package.json
```

## License

MIT
