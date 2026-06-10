// @ts-check
import { defineConfig } from "astro/config";

import mdx from "@astrojs/mdx";

import tailwindcss from "@tailwindcss/vite";

// https://astro.build/config
export default defineConfig({
  site: "https://designcode.github.io",
  integrations: [mdx()],
  redirects: {
    "/posts/2014-10-14-euro-trip-part-1": "/posts/euro-trip-part-1",
    "/posts/2015-04-20-euro-trip-part-2": "/posts/euro-trip-part-2",
    "/posts/2015-10-07-balkans-in-hd": "/posts/balkans-in-hd",
    "/posts/2017-02-25-buzludzha": "/posts/a-night-at-buzludzha",
    "/posts/2022-08-21-fjallraven-classic":
      "/posts/fjallraven-classic-with-kebnekaise",
    "/posts/2025-02-16-barcelona-half-marathon": "/posts/races-2025",
    "/posts/zevenheuvelenloop-2025": "/posts/races-2025",
    "/posts/2025-08-25-col-di-lana": "/posts/dolomites-2025",
    "/posts/2025-08-26-monte-civetta": "/posts/dolomites-2025",
  },
  vite: {
    plugins: [tailwindcss()],
  },
});
