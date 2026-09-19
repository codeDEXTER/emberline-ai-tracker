# Search discoverability and SEO

This guide records the practical SEO strategy for Emberline. It distinguishes
the GitHub repository surface from the optional static HTML pages: Google can
index a hosted page, while GitHub discovery is driven primarily by the
repository name, description, topics, README, links, and activity.

## Current strengths

- The repository name is descriptive: `emberline-ai-tracker`.
- The description and topics identify AI agents, shared memory, project
  tracking, Claude Code, and OpenAI Codex.
- The README has one clear product title, a problem statement, a visual first
  fold, descriptive image alt text, and links to the tracker and user guide.
- The HTML marketing page has a unique title, a concise description, semantic
  headings, descriptive links, and accessible image alt text.
- The guide creates crawlable internal links around the main concepts rather
  than repeating keyword-heavy copy.

## Recommended search terms

Use these naturally where they describe the content, not as a repeated list:

- AI agent memory
- shared project context for AI agents
- Claude Code and OpenAI Codex workflow
- AI project tracker
- proposal and decision tracker
- warm-up and reheat session context
- developer workflow handoff

The primary phrase should remain the product explanation: **shared memory and
delivery tracker for AI agents**. Search engines reward useful, distinct
content more than keyword repetition.

## Hosted-page checklist

If `docs/warmup-reheat.html` is later hosted at a stable HTTPS URL:

1. Give each public page a unique, concise `<title>` and meta description.
2. Add a canonical URL only once the permanent URL is known.
3. Add Open Graph and social preview metadata using a representative image.
4. Add `WebSite` and `SoftwareApplication` structured data only when the
   visible page supports those claims.
5. Publish a sitemap containing only canonical public URLs and reference it
   from `robots.txt`.
6. Verify mobile rendering, image dimensions, alt text, crawlable links, and
   structured data in Search Console or the relevant validation tools.

Do not add invented canonical URLs, fake ratings, or `noindex` rules to a page
that is intended to be discovered. A sitemap is helpful for a hosted site but
is not a substitute for useful content and external links.

## GitHub discovery checklist

- Keep the root README short, specific, and useful to a first-time visitor.
- Maintain an accurate repository description and a focused set of topics.
- Link from the README to the user guide, live tracker, license, and examples.
- Use descriptive filenames, headings, link text, and image alt text.
- Publish meaningful releases and changes so the project has a continuing
  public trail.
- Earn relevant external links and citations from genuine users and projects;
  do not manufacture backlinks or stuff metadata.

## Evidence and sources

This guidance follows Google's official documentation on [title links],
[developer SEO], [the SEO Starter Guide], [site names], and [image SEO], plus
GitHub's guidance on [repository READMEs] and [repository topics].

[title links]: https://developers.google.com/search/docs/appearance/title-link
[developer SEO]: https://developers.google.com/search/docs/fundamentals/get-started-developers
[the SEO Starter Guide]: https://developers.google.com/search/docs/fundamentals/seo-starter-guide
[site names]: https://developers.google.com/search/docs/appearance/site-names
[image SEO]: https://developers.google.com/search/docs/appearance/google-images
[repository READMEs]: https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-readmes
[repository topics]: https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/classifying-your-repository-with-topics
