# LeonBlog — Codex Project Instructions

## 1. Project Overview

LeonBlog is a long-term personal static blog project.

The project is being built from scratch instead of using an existing static-site framework such as Hexo.

The main goals are:

- Keep the website fully static.
- Keep the architecture simple, transparent, and maintainable.
- Use `.tex` files as the primary article source format.
- Convert `.tex` content into HTML during the build process.
- Provide high-quality rendering for mathematical formulas.
- Organize content by subject and discipline rather than by publication date.
- Develop and preview the website locally first.
- Deploy the generated static website to the user's Alibaba Cloud ECS server through Nginx after the local version is stable.
- Keep the source code in GitHub.

This is a personal knowledge website rather than a traditional chronological blog.

---

## 2. Core Design Philosophy

When modifying this project, prefer:

1. Simplicity
2. Static generation
3. Explicit project structure
4. Predictable behavior
5. Maintainability
6. Minimal unnecessary dependencies
7. Clear separation between content and website code

Do not introduce a large framework or complex infrastructure unless there is a clear technical reason.

Do not convert LeonBlog into a dynamic website unless explicitly requested.

Do not introduce databases, backend application servers, CMS systems, or runtime content generation without explicit approval.

The final deployed website should ideally consist primarily of static resources such as:

- HTML
- CSS
- JavaScript
- Images
- Fonts or other necessary assets

---

## 3. Repository Structure

The repository root is `LeonBlog`.

One important directory is:

```text
LeonBlog/
├── AGENTS.md
├── webcode/
└── ...
```

`webcode/` is used for website framework code and related implementation.

Content should remain logically separated from website implementation.

Before creating, deleting, renaming, or moving directories:

1. Inspect the existing repository structure.
2. Preserve existing naming conventions.
3. Do not assume that a directory is unused merely because it is currently empty.
4. Do not reorganize the repository without an explicit reason.

When the current repository structure conflicts with an assumption in this file, inspect the existing files first and preserve established project decisions unless the user explicitly requests a redesign.

---

## 4. Content Organization

LeonBlog organizes articles primarily by academic discipline.

The hierarchy is conceptually similar to:

```text
Category
└── Subject
    └── Chapter / Article
```

Example:

```text
Math
├── MathematicalAnalysis
├── ComplexAnalysis
├── ProbabilityTheory
└── ...

Cryptography
├── ...
└── ...

ComputerScience
├── ...
└── ...
```

The exact directory names in the repository are the source of truth.

Do not invent new category names when an existing category already represents the same concept.

---

## 5. File and Directory Naming

Filesystem paths should use English names.

Prefer:

```text
Math/
ComplexAnalysis/
Chapter01/
```

instead of Chinese filesystem paths.

The purpose is to make:

- scripts easier to write,
- URLs cleaner,
- deployment more portable,
- Git operations more reliable,
- future automation simpler.

Chinese names are still used in the user interface.

Therefore:

> English names are for paths and internal identifiers.  
> Chinese names are for human-readable display.

Do not rename existing English paths back to Chinese.

Do not automatically translate or rename directories unless explicitly requested.

---

## 6. Metadata Is the Source of Display Information

Each content directory may contain a `meta.json` file.

`meta.json` should be used as the structured source of metadata required by the website.

Typical metadata may include information such as:

- Chinese display name
- English/internal name if necessary
- chapter title
- subject title
- display order
- navigation information
- other future presentation metadata

The exact schema may evolve.

Before adding new metadata fields:

1. Inspect existing `meta.json` files.
2. Follow the existing schema.
3. Use consistent naming across the project.
4. Avoid duplicating information unnecessarily.

Do not create multiple incompatible metadata formats for different subjects.

### Current Subject Metadata Schema

`Math/M01-LinearAlgebra/meta.json` establishes the current subject-level format:

```json
{
  "title": "线性代数",
  "order": 2,
  "chapters": [
    {
      "order": 1,
      "file": "00-introduction.tex",
      "title": "导言"
    },
    {
      "order": 2,
      "file": "01-matrices.tex",
      "title": "矩阵"
    }
  ]
}
```

Field meanings:

| Field | Type | Meaning |
| --- | --- | --- |
| `title` | string | Chinese display title of the subject. |
| `order` | integer | Subject display order within its parent category; smaller values appear first. |
| `chapters` | array of objects | Chapter entries for this subject. |
| `chapters[].order` | integer | Chapter display order within this subject; smaller values appear first. |
| `chapters[].file` | string | Source `.tex` filename, resolved relative to the directory containing this `meta.json`. |
| `chapters[].title` | string | Chinese display title of the chapter. |

Use this format when adding metadata for other subjects with the same structure.
One subject-level `meta.json` describes the subject and its chapter files; separate chapter directories or per-chapter metadata files are not required by this format.

Generate subject and chapter navigation labels from the corresponding `title` fields, and sort by the corresponding `order` fields rather than filesystem enumeration, filename prefixes, or array position.
The metadata order is independent of the numbering in paths: this example deliberately records subject `order: 2` in `M01-LinearAlgebra`, and chapter `order: 1` for `00-introduction.tex`. Do not automatically make these numbers match.

The `file` value must match the actual source filename, including its numeric prefix and `.tex` extension. When renaming a referenced source file, update its metadata entry as well.
Display titles do not have to be literal translations of filenames: `00-introduction.tex` is displayed as `导言` in this example.
Changing a display title should not rename the source file or change its path-based identity.

When implementing the build, validate field types and referenced source files, and report problems with the affected metadata path and field. This documents the metadata convention; it does not mean a metadata reader or build pipeline has already been implemented.

---

## 7. Chinese Chapter Titles

A key architectural decision is:

**Chapter Chinese names should be stored in metadata rather than extracted from `.tex` files whenever possible.**

For the current subject format, Chinese chapter titles are stored in `chapters[].title` in the subject's `meta.json`, alongside the corresponding `.tex` filenames in `chapters[].file`.

This allows the build system to generate navigation without opening and parsing every `.tex` document merely to discover its title.

Therefore, do not implement navigation logic that depends on parsing article body content when the required information can be obtained from `meta.json`.

Metadata should describe the content.

`.tex` files should contain the actual article content.

---

## 8. `.tex` as the Content Source

The primary source format for technical articles is `.tex`.

The intended pipeline is conceptually:

```text
.tex source
    ↓
build system
    ↓
HTML
    ↓
static website
```

The source `.tex` file should remain the editable canonical article source.

Do not replace the `.tex` source with generated HTML.

Generated HTML should be treated as build output.

When implementing `.tex` processing, pay special attention to:

- mathematical formulas,
- inline mathematics,
- display mathematics,
- headings,
- paragraphs,
- lists,
- code blocks,
- figures,
- tables,
- references where applicable.

Mathematical rendering quality is an important project requirement.

---

## 9. Build System

The project will use an automated build process.

A Python build script such as `build.py` may be used as the central build entry point.

The build system should eventually be able to perform tasks such as:

1. Scan the content directory.
2. Discover categories and subjects.
3. Read `meta.json`.
4. Determine display order.
5. Build the navigation hierarchy.
6. Convert `.tex` documents into HTML.
7. Inject generated content into page templates.
8. Generate subject and chapter navigation.
9. Copy required static assets.
10. Generate the final static website.
11. Support local preview and testing.

The build process should be deterministic.

Running the same build against the same source files should produce equivalent output.

Avoid unnecessary manual steps.

---

## 10. Navigation Design

The left sidebar is an important part of LeonBlog.

Its purpose is to represent the content hierarchy.

The intended structure is approximately:

```text
Major Category
    Subject
        Chapter
        Chapter
        Chapter
```

For example:

```text
Math
├── 数学分析
│   ├── 第一章
│   ├── 第二章
│   └── 第三章
├── 复变函数
│   ├── 第一章
│   └── 第二章
└── 概率论
```

The sidebar should use an accordion-style interaction.

The hierarchy should not be reconstructed from article text.

Prefer generating it from:

```text
directory structure + meta.json
```

The filesystem provides structural information.

Metadata provides human-readable names and ordering information.

---

## 11. Sidebar Behavior

When implementing the sidebar:

- Major categories should contain subjects.
- Subjects should contain their chapters or articles.
- Subjects should be expandable and collapsible.
- The current subject or chapter should be visually identifiable.
- Expanding one section should behave predictably.
- Deeply nested content should remain readable.
- Navigation generation should be automatic rather than manually hard-coded into HTML.

Do not maintain a separate hard-coded navigation list if the same information can be generated from the content tree.

---

## 12. Separation of Responsibilities

Keep these concepts separate:

### Content

Contains academic knowledge and article source files.

Examples:

```text
.tex
meta.json
article-related images
```

### Website Framework

Contains reusable site implementation.

Examples:

```text
HTML templates
CSS
JavaScript
build scripts
navigation generation
layout components
```

### Generated Output

Contains files produced by the build process.

Examples:

```text
.html
generated indexes
compiled static resources
```

Do not mix generated output with canonical content unless the project structure explicitly requires it.

---

## 13. Front-End Principles

The UI should remain clean and suitable for long-form academic reading.

Prioritize:

- readability,
- mathematical content,
- clear hierarchy,
- stable layout,
- responsive behavior,
- simple navigation.

Avoid adding visual effects merely for decoration.

Animations should only be used when they improve interaction, for example:

- sidebar accordion transitions,
- navigation feedback,
- subtle page interactions.

Academic content should remain the visual focus.

---

## 14. Mathematical Content

LeonBlog contains mathematics-heavy material.

Any implementation decision involving content rendering should consider mathematical notation first.

Do not choose a Markdown, HTML, or template solution that significantly degrades mathematical rendering merely because it is easier to implement.

If multiple implementations are available, prefer the one that:

- preserves mathematical semantics,
- handles common LaTeX notation,
- produces stable browser rendering,
- works in a static deployment.

---

## 15. URLs

URLs should preferably derive from English filesystem names or stable identifiers.

Prefer URLs such as:

```text
/math/complex-analysis/chapter-1/
```

over URLs containing filesystem-dependent Chinese paths.

Display text may still be Chinese.

Do not couple display names directly to URLs.

Changing a Chinese display title should ideally not require changing the underlying URL.

---

## 16. Local Development First

Development should follow this workflow:

```text
source files
    ↓
local build
    ↓
local preview
    ↓
verification
    ↓
Git commit
    ↓
deployment
```

Do not make deployment the primary development environment.

Features should be tested locally whenever possible before being deployed to the server.

---

## 17. Deployment

The production target is an Alibaba Cloud ECS server.

The server uses Ubuntu and Nginx.

LeonBlog is intended to be served as a static website.

Deployment should therefore remain simple:

```text
generated static files
        ↓
server web root
        ↓
Nginx
        ↓
HTTPS website
```

Do not introduce a Node.js/Python application server merely to serve static pages unless explicitly requested.

Nginx should remain responsible for serving the production static website.

---

## 18. Domain and ICP Footer

The site has an ICP filing requirement.

The website footer should retain the ICP filing information and link to:

```text
https://beian.miit.gov.cn
```

The filing information should remain accessible from the website footer.

Do not remove it while modifying layouts.

Footer styling should remain visually unobtrusive and compatible with the overall site design.

---

## 19. Git and GitHub

GitHub is used for source-code management.

When working with Git:

- Do not change repository remotes without explicit instruction.
- Do not rewrite Git history unless explicitly requested.
- Do not force-push by default.
- Do not commit secrets.
- Do not commit server credentials.
- Do not commit private keys.
- Do not commit API tokens.

Before suggesting destructive Git operations, inspect the repository state.

Prefer reversible operations.

---

## 20. Generated Files

Generated files should not become the source of truth.

If a file can be regenerated from:

```text
content + metadata + templates
```

then changes should normally be made to the source instead of editing the generated result manually.

If generated output is committed to Git, preserve whatever repository convention is already being used.

Do not arbitrarily add or remove generated output from version control.

---

## 21. Dependency Policy

Before adding a dependency, ask:

- Is it actually necessary?
- Can the same result be achieved with existing dependencies?
- Does it significantly complicate deployment?
- Does it introduce a runtime server requirement?
- Is the project still understandable without framework-specific knowledge?

Prefer small, stable dependencies.

Avoid introducing large frontend frameworks when plain HTML/CSS/JavaScript is sufficient.

Avoid introducing large site generators unless explicitly requested.

---

## 22. Coding Style

When adding code:

- Prefer readable code over clever code.
- Use meaningful variable and function names.
- Keep functions focused on one responsibility.
- Add comments when behavior is not obvious.
- Avoid unnecessary abstraction.
- Avoid premature generalization.
- Preserve existing formatting conventions.

For build scripts, failures should produce useful error messages.

For example, if metadata is invalid, report:

- the affected file,
- the invalid field,
- the expected format if known.

Do not silently ignore malformed content unless there is a deliberate fallback.

---

## 23. Content Discovery

The build system should discover content automatically from the project structure.

Avoid code like:

```text
subjects = [
    "MathematicalAnalysis",
    "ComplexAnalysis",
    "ProbabilityTheory"
]
```

when those subjects can be discovered from directories and metadata.

Hard-coded content lists create unnecessary maintenance work.

Prefer:

```text
scan directories
→ read metadata
→ sort
→ generate navigation
```

---

## 24. Ordering

Directory enumeration order should not be relied upon for visible navigation.

If ordering matters, use explicit metadata.

This is especially important for:

- subjects,
- chapters,
- sidebar navigation,
- homepage sections.

The build result should not depend on operating-system filesystem ordering.

---

## 25. Error Handling

The build system should detect common content problems.

Examples:

- missing `meta.json`,
- invalid JSON,
- duplicate order values when problematic,
- missing referenced `.tex` files,
- invalid content paths,
- unsupported structure.

Prefer clear warnings or errors.

Do not silently generate an incomplete site when a critical input is missing.

---

## 26. Do Not Infer Unconfirmed Architecture

Some details of LeonBlog are still evolving.

Therefore:

- Do not invent a new metadata schema without inspecting existing files.
- Do not invent directory names.
- Do not rename directories for stylistic reasons.
- Do not assume the build output directory name.
- Do not assume a specific `.tex` conversion engine until the repository establishes one.
- Do not replace an existing implementation merely because another library is more popular.

Inspect first.

Then modify the smallest necessary part.

---

## 27. Preserve Previous Design Decisions

This project is being designed incrementally.

When modifying an existing component, treat previous architectural decisions as intentional unless evidence indicates otherwise.

In particular, preserve these decisions:

- LeonBlog is a static website.
- It is not based on Hexo.
- `.tex` is a primary content source.
- Content is organized by academic subject rather than chronology.
- Filesystem paths should use English names.
- Chinese names should be stored as presentation metadata.
- `meta.json` should provide navigation/display metadata.
- Chapter titles should not need to be extracted from `.tex` merely to build navigation.
- Sidebar navigation should be generated automatically.
- The sidebar should support accordion-style subject/chapter navigation.
- Website code and article content should remain separated.
- The project should be locally previewable before deployment.
- Production is served through Nginx as a static website.

Do not reverse these decisions without explicit user instruction.

---

## 28. How Codex Should Approach Tasks

Before editing the project:

1. Inspect the relevant files.
2. Inspect the directory tree.
3. Read nearby `meta.json` files when working with content structure.
4. Understand the existing implementation.
5. Identify the smallest set of files that need modification.

When implementing:

1. Preserve current architecture.
2. Make focused changes.
3. Avoid unrelated refactoring.
4. Keep generated content deterministic.
5. Maintain backward compatibility with existing content whenever practical.

After implementing:

1. Check for syntax errors.
2. Run the relevant build or validation command when available.
3. Verify generated paths and navigation when relevant.
4. Report what was changed.
5. Report any assumptions that remain.

---

## 29. Avoid Unrelated Changes

When asked to implement one feature, do not simultaneously:

- redesign the entire UI,
- rename unrelated files,
- reorganize the repository,
- replace libraries,
- change deployment architecture,
- alter metadata conventions,
- rewrite unrelated code.

Keep commits and modifications focused.

---

## 30. Preferred Decision Rule

When uncertain between two solutions, prefer the one that is:

```text
simpler
+ more static
+ easier to understand
+ easier to maintain
+ easier to regenerate
+ less dependent on framework magic
```

unless there is a strong technical reason to choose otherwise.

---

## 31. Project Source of Truth

When information conflicts, use the following priority:

1. Explicit current user instruction
2. Existing repository structure and implementation
3. Existing metadata conventions
4. This `AGENTS.md`
5. General assumptions or common framework conventions

Never override an explicit project decision merely because another convention is more common.

---

## 32. Current Development Principle

LeonBlog is still under active architectural development.

Do not rush into generating large amounts of implementation code when the user is still defining:

- directory structure,
- metadata structure,
- navigation hierarchy,
- templates,
- build behavior.

When architecture has not yet been finalized, help preserve flexibility.

Once a convention has been explicitly established, follow it consistently throughout the project.
