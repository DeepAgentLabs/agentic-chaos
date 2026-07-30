# agentic-chaos Website

Modern, responsive website for the agentic-chaos project.

## 📁 Structure

```
website/
├── index.html                 # Landing page (hero, features, faults, quick start)
├── docs/
│   └── index.html            # Full documentation
├── blog/
│   └── index.html            # Blog posts & case studies
├── explorer/
│   └── index.html            # Interactive fault explorer/visualizer
├── assets/
│   ├── css/
│   │   └── main.css          # Main stylesheet (dark mode support)
│   └── js/
│       └── main.js           # Utilities (smooth scroll, animations)
├── _config.yml               # GitHub Pages configuration
└── .nojekyll                 # Tell GitHub Pages to skip Jekyll processing
```

## 🚀 Deployment

### GitHub Pages (Automatic)

1. Enable GitHub Pages in repo settings
2. Set source to `branch: main, folder: /website`
3. Site builds automatically on push

**URL:** `https://deepagentlabs.github.io/agentic-chaos`

### Local Preview

Open `index.html` in your browser or use a local server:

```bash
python -m http.server 8000
# Visit http://localhost:8000/website
```

## 🎨 Customization

### Colors

Edit CSS variables in `assets/css/main.css`:

```css
:root {
    --primary: #00b366;        /* Green */
    --secondary: #1e88e5;      /* Blue */
    --accent: #ff6b35;         /* Orange */
}
```

### Content

- **Landing Page:** Edit `index.html` sections
- **Docs:** Update `docs/index.html` with new sections
- **Blog:** Add new `.html` files in `blog/` or update `blog/index.html`
- **Explorer:** Modify fault data in `explorer/index.html`

### Branding

Replace emojis, copy, and links:
- Logo: `🌪️` emoji in `<span class="logo-emoji">`
- Company: "DeepAgentLabs" throughout
- Links: GitHub, PyPI, etc.

## 📱 Responsive Design

All pages are mobile-first, responsive across:
- Desktop (1200px+)
- Tablet (768px–1199px)
- Mobile (<768px)

## ✨ Features

- **Dark Mode Support** – Auto-detects user preference
- **Smooth Scrolling** – Navigation animations
- **Interactive Fault Explorer** – Demo fault behaviors
- **Case Studies** – Real-world examples
- **Zero Dependencies** – Pure HTML/CSS/JS, no frameworks
- **GitHub Pages Ready** – One-click deployment

## 🔗 Pages

| Page | Path | Purpose |
|------|------|---------|
| Landing | `/` | Hero, features, faults, quick start |
| Docs | `/docs/` | Full API reference & guides |
| Blog | `/blog/` | Case studies & announcements |
| Explorer | `/explorer/` | Interactive fault playground |

## 📝 SEO

Each page includes:
- Descriptive meta tags
- Semantic HTML
- Open Graph tags (ready for social sharing)

## 🤝 Contributing

To contribute website improvements:

1. Edit files in `website/` folder
2. Test locally
3. Commit to `feature/update` branch
4. Open PR with changes
5. Site deploys automatically after merge

## 📄 License

Website content © 2026 DeepAgentLabs. MIT License.
