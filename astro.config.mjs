// @ts-check
import { defineConfig } from "astro/config";

import mdx from "@astrojs/mdx";

import tailwindcss from "@tailwindcss/vite";

// https://astro.build/config
export default defineConfig({
  site: "https://designcode.github.io",
  integrations: [mdx()],
  redirects: {
    "/2017/04/14/northern-lights-what-when-and-where":
      "/northern-lights-what-when-and-where",
    "/2019/09/21/the-ultimate-guide-of-driving-around-iceland-in-8-days":
      "/the-ultimate-guide-of-driving-around-iceland-in-8-days",
    "/2019/10/24/5-days-and-nights-and-tromso": "/5-days-and-nights-in-tromso",
    "/2019/10/16/5-days-in-madeira": "/5-days-in-madeira",
    "/2019/10/05/5-days-in-sicily": "/5-days-in-sicily",
    "/2019/10/29/1-day-hike-on-matterhorn-trail": "/matterhorn",
    "/2019/10/05/mount-etna-easy-intermediate-and-advance-hikes": "/etna",
    "/2019/09/21/rocciamelone-from-susa-to-peak": "/rocciamelone",
    "/2019/09/15/kebnekaise-climbing-the-highest-peak-of-sweden": "/kebnekaise",
    "/2017/04/15/mount-teide-a-guide-to-reach-the-peak": "/teide",
    "/2019/09/14/triglav-a-guide-to-reach-top-of-slovenia": "/triglav",
    "/posts/2014-10-14-euro-trip-part-1": "/euro-trip-part-1",
    "/posts/2015-04-20-euro-trip-part-2": "/euro-trip-part-2",
    "/posts/2015-10-07-balkans-in-hd": "/balkans-in-hd",
    "/posts/2017-02-25-buzludzha": "/a-night-at-buzludzha",
    "/posts/2022-08-21-fjallraven-classic":
      "/fjallraven-classic-with-kebnekaise",
    "/posts/2025-02-16-barcelona-half-marathon": "/races-2025",
    "/posts/zevenheuvelenloop-2025": "/races-2025",
    "/posts/2025-08-25-col-di-lana": "/dolomites-2025",
    "/posts/2025-08-26-monte-civetta": "/dolomites-2025",
    // Posts used to live under /posts/<slug>; they are now at /<slug>.
    // Static entries above take priority over this dynamic one.
    "/posts/[slug]": "/[slug]",
  },
  vite: {
    plugins: [tailwindcss()],
  },
});
