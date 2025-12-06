# Music Hub - Feature Testing Checklist

## Test Date: December 5, 2025
## Test Environment: Local (http://127.0.0.1:5001)

---

## ✅ Core Functionality

### Homepage (News Page)
- [ ] Page loads successfully
- [ ] Articles display in grid layout
- [ ] Images load properly
- [ ] Article titles are clickable
- [ ] Descriptions are truncated at 150 characters
- [ ] Published dates show correctly

### Search Functionality
- [ ] Search bar is visible on all pages
- [ ] Can search for artists (e.g., "Metallica")
- [ ] Search results are relevant
- [ ] Search uses Loudwire's search RSS feed
- [ ] No search query shows latest news

### Releases Page
- [ ] Page loads with today's date
- [ ] Default year range is last 20 years (no error message)
- [ ] Can change date using date picker
- [ ] Can adjust year range
- [ ] Results display in table format
- [ ] Album covers show in table (or music note placeholder)
- [ ] Table has: Cover, Year, Artist, Title, Link columns
- [ ] Results are sorted by year (newest first)
- [ ] Cached results load faster on repeat searches

### Article Proxy Page
- [ ] Clicking article opens proxy page
- [ ] Article title displays (only once, not duplicated)
- [ ] Featured image shows at top
- [ ] Article content displays properly
- [ ] No duplicate images in content
- [ ] "Back to News" link works
- [ ] Source link to Loudwire is present

---

## 🎨 New Features (Top 5)

### 1. Dark/Light Mode Toggle
- [ ] Theme toggle button (🌙/☀️) appears on all pages
- [ ] Clicking toggle switches between dark and light themes
- [ ] Theme preference persists after page refresh
- [ ] Light theme colors are readable
- [ ] Dark theme colors are readable
- [ ] All pages respect theme setting (News, Releases, Article)
- [ ] Smooth transition between themes

### 2. Bookmark System
- [ ] Star button (☆) appears on each article card
- [ ] Clicking star bookmarks article (turns to ★)
- [ ] Clicking again un-bookmarks article
- [ ] Bookmarks persist after page refresh
- [ ] Bookmarked state shows on page load
- [ ] Can bookmark multiple articles
- [ ] localStorage stores bookmarks correctly

### 3. Loading States & Skeleton Loaders
- [ ] Skeleton cards defined in CSS
- [ ] Smooth animation on skeleton loaders
- [ ] Ready for async loading implementation
- [ ] CSS classes work properly (.skeleton, .skeleton-card)

### 4. Social Sharing Buttons
- [ ] Share buttons appear on each article card
- [ ] Twitter share button works (opens popup)
- [ ] Facebook share button works (opens popup)
- [ ] Reddit share button works (opens popup)
- [ ] Copy link button works (copies to clipboard)
- [ ] "Link copied!" message appears briefly
- [ ] Buttons have proper icons (🐦, 📘, 🔴, 🔗)
- [ ] Share buttons styled properly

### 5. Pagination
- [ ] Pagination appears when >20 articles
- [ ] Shows 20 articles per page
- [ ] Page numbers display (up to 5 visible)
- [ ] "Previous" button works
- [ ] "Next" button works
- [ ] Clicking page number navigates to that page
- [ ] Active page is highlighted
- [ ] Previous/Next buttons disabled at boundaries
- [ ] Scrolls to top when changing pages

---

## 🔍 Additional Features

### Recent Search History
- [ ] Focus on search input shows recent searches dropdown
- [ ] Last 10 searches are stored
- [ ] Clicking recent search performs that search
- [ ] Recent searches persist across sessions
- [ ] Dropdown closes when clicking outside

### Navigation
- [ ] Header is sticky (stays at top when scrolling)
- [ ] Active page is highlighted in navigation
- [ ] All navigation links work
- [ ] Logo/title is clickable (returns to homepage)

### SEO & Discoverability
- [ ] /sitemap.xml loads and shows URLs
- [ ] /robots.txt loads and allows crawling
- [ ] Meta tags are present in HTML

### GitHub Action (Keep-Alive)
- [ ] Action exists in .github/workflows/keep-alive.yml
- [ ] Scheduled to run every 10 minutes
- [ ] Can be manually triggered
- [ ] Check GitHub Actions tab for execution

---

## 📱 Responsive Design

### Mobile View (< 640px)
- [ ] Grid adjusts to single column
- [ ] Search bar spans full width
- [ ] Navigation stacks vertically
- [ ] Cards are touch-friendly
- [ ] Buttons are adequately sized
- [ ] Table scrolls horizontally on releases page

### Tablet View (640-1024px)
- [ ] Grid shows 2 columns
- [ ] Layout is balanced
- [ ] All features accessible

### Desktop View (> 1024px)
- [ ] Grid shows 3-4 columns
- [ ] Max width of 1200px maintained
- [ ] All features accessible

---

## 🚀 Performance

### Load Times
- [ ] Homepage loads in < 3 seconds
- [ ] Releases page loads in < 3 seconds
- [ ] Article proxy loads in < 2 seconds
- [ ] Images load progressively (lazy loading)

### Caching
- [ ] Release searches are cached for 30 days
- [ ] SQLite database stores cached data
- [ ] Repeat searches load instantly from cache

---

## 🐛 Error Handling

### Expected Errors
- [ ] Invalid date shows error message
- [ ] Year range > 25 years shows warning
- [ ] Failed RSS fetch shows error message
- [ ] Broken images fall back to default
- [ ] No articles found shows helpful message

### Edge Cases
- [ ] Search with special characters works
- [ ] Empty search shows latest articles
- [ ] Very long article titles don't break layout
- [ ] Missing album covers show placeholder (♪)
- [ ] Article proxy handles missing images

---

## 🔒 Security & Best Practices

- [ ] No console errors in browser
- [ ] No broken links (404s)
- [ ] External links open in new tab (_blank)
- [ ] rel="noopener noreferrer" on external links
- [ ] CORS properly configured
- [ ] User data only stored in localStorage (no server storage)

---

## 📊 Browser Compatibility

Test in:
- [ ] Chrome/Edge (Chromium)
- [ ] Firefox
- [ ] Safari (macOS/iOS)
- [ ] Mobile browsers (iOS Safari, Chrome Mobile)

---

## 🎯 Known Issues / Future Improvements

### Issues Found:
1. 
2. 
3. 

### Notes:
- HTML linter shows false errors for Jinja2 templates (expected)
- Skeleton loaders CSS ready but need async implementation for full effect
- Pagination only appears with >20 articles (test with broader search)

---

## Test Results Summary

**Date Tested:** _____________
**Tester:** _____________
**Overall Status:** ⬜ Pass  ⬜ Pass with Minor Issues  ⬜ Fail

**Features Working:** _____ / 50+
**Critical Issues:** _____
**Minor Issues:** _____

**Deployment Ready:** ⬜ Yes  ⬜ No  ⬜ With Fixes
