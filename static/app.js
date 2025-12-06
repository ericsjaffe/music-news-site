// Theme Toggle
function initThemeToggle() {
  const themeToggle = document.getElementById('theme-toggle');
  const html = document.documentElement;
  
  // Load saved theme or default to dark
  const savedTheme = localStorage.getItem('theme') || 'dark';
  html.setAttribute('data-theme', savedTheme);
  updateThemeIcon(savedTheme);
  
  if (themeToggle) {
    themeToggle.addEventListener('click', () => {
      const currentTheme = html.getAttribute('data-theme');
      const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
      
      html.setAttribute('data-theme', newTheme);
      localStorage.setItem('theme', newTheme);
      updateThemeIcon(newTheme);
    });
  }
}

function updateThemeIcon(theme) {
  const themeToggle = document.getElementById('theme-toggle');
  if (themeToggle) {
    themeToggle.textContent = theme === 'dark' ? '☀️' : '🌙';
  }
}

// Bookmark System
function initBookmarks() {
  // Load bookmarks from localStorage
  const bookmarks = JSON.parse(localStorage.getItem('bookmarks') || '[]');
  
  // Update UI for all bookmark buttons
  document.querySelectorAll('.bookmark-btn').forEach(btn => {
    const articleUrl = btn.dataset.url;
    if (bookmarks.includes(articleUrl)) {
      btn.classList.add('bookmarked');
      btn.textContent = '★';
    }
    
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      toggleBookmark(articleUrl, btn);
    });
  });
}

function toggleBookmark(url, button) {
  let bookmarks = JSON.parse(localStorage.getItem('bookmarks') || '[]');
  
  if (bookmarks.includes(url)) {
    // Remove bookmark
    bookmarks = bookmarks.filter(b => b !== url);
    button.classList.remove('bookmarked');
    button.textContent = '☆';
  } else {
    // Add bookmark
    bookmarks.push(url);
    button.classList.add('bookmarked');
    button.textContent = '★';
  }
  
  localStorage.setItem('bookmarks', JSON.stringify(bookmarks));
}

// Show bookmarked articles
function showBookmarks() {
  const bookmarks = JSON.parse(localStorage.getItem('bookmarks') || '[]');
  return bookmarks;
}

// Recent Searches
function initRecentSearches() {
  const searchInput = document.querySelector('input[name="q"]');
  const searchForm = searchInput?.closest('form');
  
  if (searchForm) {
    searchForm.addEventListener('submit', (e) => {
      const query = searchInput.value.trim();
      if (query) {
        addRecentSearch(query);
      }
    });
  }
  
  // Load and display recent searches if input is focused
  if (searchInput) {
    searchInput.addEventListener('focus', () => {
      displayRecentSearches(searchInput);
    });
  }
}

function addRecentSearch(query) {
  let searches = JSON.parse(localStorage.getItem('recentSearches') || '[]');
  
  // Remove if already exists
  searches = searches.filter(s => s !== query);
  
  // Add to beginning
  searches.unshift(query);
  
  // Keep only last 10
  searches = searches.slice(0, 10);
  
  localStorage.setItem('recentSearches', JSON.stringify(searches));
}

function displayRecentSearches(input) {
  const searches = JSON.parse(localStorage.getItem('recentSearches') || '[]');
  
  if (searches.length === 0) return;
  
  // Remove existing dropdown if any
  const existing = document.getElementById('recent-searches-dropdown');
  if (existing) existing.remove();
  
  // Create dropdown
  const dropdown = document.createElement('div');
  dropdown.id = 'recent-searches-dropdown';
  dropdown.style.cssText = `
    position: absolute;
    top: 100%;
    left: 0;
    right: 0;
    background: var(--bg-card);
    border: 1px solid var(--border-color);
    border-radius: 0.5rem;
    margin-top: 0.5rem;
    box-shadow: 0 10px 40px rgba(0, 0, 0, 0.3);
    z-index: 1000;
    max-height: 300px;
    overflow-y: auto;
  `;
  
  searches.forEach(search => {
    const item = document.createElement('a');
    item.href = `/?q=${encodeURIComponent(search)}`;
    item.textContent = search;
    item.style.cssText = `
      display: block;
      padding: 0.75rem 1rem;
      color: var(--text-primary);
      text-decoration: none;
      border-bottom: 1px solid var(--border-color);
      transition: background 0.2s;
    `;
    item.addEventListener('mouseenter', () => {
      item.style.background = 'var(--bg-tertiary)';
    });
    item.addEventListener('mouseleave', () => {
      item.style.background = 'transparent';
    });
    dropdown.appendChild(item);
  });
  
  // Position relative to search input
  const container = input.parentElement;
  container.style.position = 'relative';
  container.appendChild(dropdown);
  
  // Close on click outside
  setTimeout(() => {
    document.addEventListener('click', function closeDropdown(e) {
      if (!container.contains(e.target)) {
        dropdown.remove();
        document.removeEventListener('click', closeDropdown);
      }
    });
  }, 100);
}

// Social Sharing
function shareOnTwitter(title, url) {
  const text = encodeURIComponent(title);
  const shareUrl = encodeURIComponent(url);
  window.open(`https://twitter.com/intent/tweet?text=${text}&url=${shareUrl}`, '_blank', 'width=550,height=420');
}

function shareOnFacebook(url) {
  const shareUrl = encodeURIComponent(url);
  window.open(`https://www.facebook.com/sharer/sharer.php?u=${shareUrl}`, '_blank', 'width=550,height=420');
}

function shareOnReddit(title, url) {
  const text = encodeURIComponent(title);
  const shareUrl = encodeURIComponent(url);
  window.open(`https://reddit.com/submit?title=${text}&url=${shareUrl}`, '_blank', 'width=550,height=420');
}

function copyToClipboard(text) {
  navigator.clipboard.writeText(text).then(() => {
    // Show temporary feedback
    const feedback = document.createElement('div');
    feedback.textContent = 'Link copied!';
    feedback.style.cssText = `
      position: fixed;
      top: 50%;
      left: 50%;
      transform: translate(-50%, -50%);
      background: var(--success);
      color: white;
      padding: 1rem 2rem;
      border-radius: 0.5rem;
      z-index: 10000;
      animation: fadeOut 2s forwards;
    `;
    document.body.appendChild(feedback);
    setTimeout(() => feedback.remove(), 2000);
  });
}

// Loading Skeletons
function showLoadingSkeletons(container, count = 12) {
  container.innerHTML = '';
  for (let i = 0; i < count; i++) {
    const skeleton = document.createElement('div');
    skeleton.className = 'skeleton-card';
    skeleton.innerHTML = `
      <div class="skeleton skeleton-image"></div>
      <div class="skeleton-body">
        <div class="skeleton skeleton-title"></div>
        <div class="skeleton skeleton-text"></div>
        <div class="skeleton skeleton-text"></div>
        <div class="skeleton skeleton-text"></div>
      </div>
    `;
    container.appendChild(skeleton);
  }
}

// Pagination
let currentPage = 1;
const articlesPerPage = 20;

function initPagination() {
  const grid = document.querySelector('.grid');
  if (!grid) return;
  
  const allArticles = Array.from(grid.children);
  
  if (allArticles.length <= articlesPerPage) return;
  
  showPage(1, allArticles, grid);
  createPaginationControls(allArticles, grid);
}

function showPage(page, articles, container) {
  const start = (page - 1) * articlesPerPage;
  const end = start + articlesPerPage;
  
  articles.forEach((article, index) => {
    article.style.display = (index >= start && index < end) ? 'flex' : 'none';
  });
  
  currentPage = page;
  
  // Scroll to top
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function createPaginationControls(articles, container) {
  const totalPages = Math.ceil(articles.length / articlesPerPage);
  
  const paginationDiv = document.createElement('div');
  paginationDiv.className = 'pagination';
  
  // Previous button
  const prevBtn = document.createElement('button');
  prevBtn.className = 'page-btn';
  prevBtn.textContent = '← Previous';
  prevBtn.onclick = () => {
    if (currentPage > 1) {
      showPage(currentPage - 1, articles, container);
      updatePaginationControls(totalPages);
    }
  };
  paginationDiv.appendChild(prevBtn);
  
  // Page numbers
  const pageNumbersDiv = document.createElement('div');
  pageNumbersDiv.id = 'page-numbers';
  pageNumbersDiv.style.display = 'flex';
  pageNumbersDiv.style.gap = '0.5rem';
  paginationDiv.appendChild(pageNumbersDiv);
  
  // Next button
  const nextBtn = document.createElement('button');
  nextBtn.className = 'page-btn';
  nextBtn.textContent = 'Next →';
  nextBtn.onclick = () => {
    if (currentPage < totalPages) {
      showPage(currentPage + 1, articles, container);
      updatePaginationControls(totalPages);
    }
  };
  paginationDiv.appendChild(nextBtn);
  
  container.after(paginationDiv);
  
  updatePaginationControls(totalPages);
}

function updatePaginationControls(totalPages) {
  const pageNumbersDiv = document.getElementById('page-numbers');
  if (!pageNumbersDiv) return;
  
  pageNumbersDiv.innerHTML = '';
  
  // Show up to 5 page numbers
  let startPage = Math.max(1, currentPage - 2);
  let endPage = Math.min(totalPages, startPage + 4);
  
  if (endPage - startPage < 4) {
    startPage = Math.max(1, endPage - 4);
  }
  
  for (let i = startPage; i <= endPage; i++) {
    const pageBtn = document.createElement('button');
    pageBtn.className = `page-btn ${i === currentPage ? 'active' : ''}`;
    pageBtn.textContent = i;
    pageBtn.onclick = () => {
      const grid = document.querySelector('.grid');
      const articles = Array.from(grid.children);
      showPage(i, articles, grid);
      updatePaginationControls(totalPages);
    };
    pageNumbersDiv.appendChild(pageBtn);
  }
  
  // Update prev/next button states
  const prevBtn = document.querySelector('.pagination .page-btn:first-child');
  const nextBtn = document.querySelector('.pagination .page-btn:last-child');
  
  if (prevBtn) {
    prevBtn.classList.toggle('disabled', currentPage === 1);
  }
  if (nextBtn) {
    nextBtn.classList.toggle('disabled', currentPage === totalPages);
  }
}

// Initialize everything on page load
document.addEventListener('DOMContentLoaded', () => {
  initThemeToggle();
  initBookmarks();
  initRecentSearches();
  initPagination();
});

// Add fade out animation
const style = document.createElement('style');
style.textContent = `
  @keyframes fadeOut {
    0% { opacity: 1; }
    70% { opacity: 1; }
    100% { opacity: 0; }
  }
`;
document.head.appendChild(style);
