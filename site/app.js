const STORAGE_KEY = "moaread-state-v1";
const PAGE_SIZE = 24;

const $ = (selector) => document.querySelector(selector);
const state = {
  articles: [],
  sources: [],
  generatedAt: null,
  view: "reading",
  disabledSources: [],
  favoriteKeywords: "",
  hiddenKeywords: "",
  interestOnly: false,
  readIds: [],
  savedIds: [],
  theme: "light",
  visibleCount: PAGE_SIZE,
  query: "",
  sort: "newest",
};

function restoreState() {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
    for (const key of ["disabledSources", "readIds", "savedIds"]) {
      if (Array.isArray(saved[key])) state[key] = saved[key].filter((value) => typeof value === "string");
    }
    for (const key of ["favoriteKeywords", "hiddenKeywords", "theme"]) {
      if (typeof saved[key] === "string") state[key] = saved[key];
    }
  } catch {
    // A damaged browser setting should not prevent the feed from opening.
  }
  applyTheme();
  $("#favorite-keywords").value = state.favoriteKeywords;
  $("#hidden-keywords").value = state.hiddenKeywords;
}

function saveState() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({
      disabledSources: state.disabledSources,
      favoriteKeywords: state.favoriteKeywords,
      hiddenKeywords: state.hiddenKeywords,
      readIds: state.readIds,
      savedIds: state.savedIds,
      theme: state.theme,
    }));
  } catch {
    showToast("브라우저 저장 공간을 사용할 수 없습니다.");
  }
}

function applyTheme() {
  document.documentElement.dataset.theme = state.theme === "dark" ? "dark" : "light";
  $("#theme-toggle").setAttribute("aria-label", state.theme === "dark" ? "라이트 모드 전환" : "다크 모드 전환");
}

function make(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function keywords(value) {
  return value.split(",").map((word) => word.trim().toLocaleLowerCase("ko")).filter(Boolean);
}

function hasSource(article) {
  return article.sourceIds.some((id) => !state.disabledSources.includes(id));
}

function isNews(article) {
  return article.sourceIds.some((id) => state.sources.find((source) => source.id === id)?.type === "news");
}

function searchText(article) {
  const sourceNames = article.sourceIds.map((id) => state.sources.find((source) => source.id === id)?.name || "").join(" ");
  return `${article.title} ${article.summary} ${sourceNames}`.toLocaleLowerCase("ko");
}

function filteredArticles() {
  const excluded = keywords(state.hiddenKeywords);
  const favorites = keywords(state.favoriteKeywords);
  const query = state.query.trim().toLocaleLowerCase("ko");
  return state.articles.filter((article) => {
    if (!hasSource(article)) return false;
    if (state.view === "reading" && isNews(article)) return false;
    if (state.view === "news" && !isNews(article)) return false;
    if (state.view === "unread" && state.readIds.includes(article.id)) return false;
    if (state.view === "saved" && !state.savedIds.includes(article.id)) return false;
    const searchable = searchText(article);
    if (query && !searchable.includes(query)) return false;
    if (excluded.some((word) => searchable.includes(word))) return false;
    if (state.interestOnly && favorites.length && !favorites.some((word) => searchable.includes(word))) return false;
    return true;
  }).sort((a, b) => state.sort === "newest" ? b.publishedAt.localeCompare(a.publishedAt) : a.publishedAt.localeCompare(b.publishedAt));
}

function formatDate(iso) {
  const date = new Date(iso);
  return Number.isNaN(date.valueOf()) ? "날짜 미상" : new Intl.DateTimeFormat("ko-KR", { year: "numeric", month: "long", day: "numeric", timeZone: "Asia/Seoul" }).format(date);
}

function showToast(message) {
  const toast = $("#toast");
  toast.textContent = message;
  toast.classList.add("visible");
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => toast.classList.remove("visible"), 3000);
}

function renderSources() {
  const list = $("#source-list");
  list.replaceChildren();
  const groups = [...new Set(state.sources.map((source) => source.group))];
  for (const group of groups) {
    list.append(make("div", "source-group-title", group));
    for (const source of state.sources.filter((item) => item.group === group)) {
      const label = make("label", "source-option");
      const input = make("input");
      input.type = "checkbox";
      input.checked = !state.disabledSources.includes(source.id);
      input.addEventListener("change", () => {
        state.disabledSources = input.checked ? state.disabledSources.filter((id) => id !== source.id) : [...state.disabledSources, source.id];
        state.visibleCount = PAGE_SIZE;
        saveState();
        render();
      });
      label.append(input, make("span", "custom-check"), make("span", "source-name", source.name));
      list.append(label);
    }
  }
}

function toggleId(key, id) {
  state[key] = state[key].includes(id) ? state[key].filter((item) => item !== id) : [...state[key], id];
  saveState();
  render();
}

function articleCard(article, index) {
  const card = make("article", `article-card${state.readIds.includes(article.id) ? " is-read" : ""}`);
  const ordinal = make("span", "article-ordinal", String(index + 1).padStart(2, "0"));
  const body = make("div", "article-body");
  const top = make("div", "article-top");
  const sources = make("div", "article-sources");
  for (const id of article.sourceIds) {
    const source = state.sources.find((item) => item.id === id);
    if (source) sources.append(make("span", "source-pill", source.name));
  }
  top.append(sources, make("time", "article-date", formatDate(article.publishedAt)));
  const title = make("h3", "article-title");
  const link = make("a", "", article.title);
  link.href = article.url;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  link.addEventListener("click", () => {
    if (!state.readIds.includes(article.id)) {
      state.readIds.push(article.id);
      saveState();
      setTimeout(render, 100);
    }
  });
  title.append(link);
  body.append(top, title);
  if (article.summary) body.append(make("p", "article-summary", article.summary));
  const bottom = make("div", "article-bottom");
  const readButton = make("button", "subtle-action", state.readIds.includes(article.id) ? "✓ 읽음" : "○ 읽음 표시");
  readButton.type = "button";
  readButton.setAttribute("aria-label", state.readIds.includes(article.id) ? `${article.title} 읽지 않음으로 표시` : `${article.title} 읽음으로 표시`);
  readButton.addEventListener("click", () => toggleId("readIds", article.id));
  const saveButton = make("button", `save-action${state.savedIds.includes(article.id) ? " saved" : ""}`, state.savedIds.includes(article.id) ? "★ 저장됨" : "☆ 저장");
  saveButton.type = "button";
  saveButton.setAttribute("aria-label", state.savedIds.includes(article.id) ? `${article.title} 저장 취소` : `${article.title} 저장`);
  saveButton.addEventListener("click", () => toggleId("savedIds", article.id));
  bottom.append(readButton, saveButton);
  body.append(bottom);
  card.append(ordinal, body);
  return card;
}

function render() {
  const titles = {
    reading: ["기술 글", "새로 올라온 기술 블로그와 커뮤니티 글을 둘러보세요."],
    news: ["국내 뉴스", "국내 IT·개발 뉴스를 따로 모았어요."],
    all: ["전체 글", "기술 글과 뉴스를 시간순으로 모았어요."],
    unread: ["읽지 않은 글", "아직 만나지 않은 글을 모았어요."],
    saved: ["저장한 글", "다시 읽고 싶은 글을 모았어요."],
  };
  $("#view-title").textContent = titles[state.view][0];
  $("#view-description").textContent = titles[state.view][1];
  document.querySelectorAll(".nav-item").forEach((item) => item.classList.toggle("active", item.dataset.view === state.view));
  const available = state.articles.filter(hasSource);
  $("#count-reading").textContent = available.filter((item) => !isNews(item)).length.toLocaleString("ko-KR");
  $("#count-news").textContent = available.filter(isNews).length.toLocaleString("ko-KR");
  $("#count-all").textContent = available.length.toLocaleString("ko-KR");
  $("#count-unread").textContent = available.filter((item) => !state.readIds.includes(item.id)).length.toLocaleString("ko-KR");
  $("#count-saved").textContent = available.filter((item) => state.savedIds.includes(item.id)).length.toLocaleString("ko-KR");
  const articles = filteredArticles();
  $("#result-count").textContent = `${articles.length.toLocaleString("ko-KR")}개의 글`;
  const summary = $("#filter-summary");
  const filters = [];
  if (state.query.trim()) filters.push(`검색: ${state.query.trim()}`);
  if (state.interestOnly && keywords(state.favoriteKeywords).length) filters.push("관심 키워드");
  if (keywords(state.hiddenKeywords).length) filters.push("숨길 키워드 적용 중");
  summary.hidden = !filters.length;
  summary.textContent = filters.join(" · ");
  const container = $("#articles");
  container.replaceChildren();
  if (!articles.length) {
    const empty = make("div", "empty-state");
    empty.append(make("div", "empty-symbol", "✳"), make("h3", "", "여기엔 아직 글이 없어요."), make("p", "", "검색어나 구독 소스, 키워드 설정을 바꿔보세요."));
    container.append(empty);
  } else {
    articles.slice(0, state.visibleCount).forEach((article, index) => container.append(articleCard(article, index)));
  }
  $("#load-more").hidden = articles.length <= state.visibleCount;
}

function bindEvents() {
  document.querySelectorAll(".nav-item").forEach((item) => item.addEventListener("click", () => {
    state.view = item.dataset.view;
    state.visibleCount = PAGE_SIZE;
    render();
    $("#main-content").scrollIntoView({ behavior: "smooth", block: "start" });
  }));
  $("#search-input").addEventListener("input", (event) => { state.query = event.target.value; state.visibleCount = PAGE_SIZE; render(); });
  $("#sort-order").addEventListener("change", (event) => { state.sort = event.target.value; render(); });
  $("#interest-only").addEventListener("change", (event) => {
    if (event.target.checked && !keywords(state.favoriteKeywords).length) {
      event.target.checked = false;
      $("#favorite-keywords").focus();
      showToast("먼저 관심 키워드를 입력해 주세요.");
      return;
    }
    state.interestOnly = event.target.checked;
    render();
  });
  for (const [selector, key] of [["#favorite-keywords", "favoriteKeywords"], ["#hidden-keywords", "hiddenKeywords"]]) {
    $(selector).addEventListener("input", (event) => {
      state[key] = event.target.value;
      state.visibleCount = PAGE_SIZE;
      if (key === "favoriteKeywords" && !keywords(state.favoriteKeywords).length) {
        state.interestOnly = false;
        $("#interest-only").checked = false;
      }
      saveState();
      render();
    });
  }
  $("#theme-toggle").addEventListener("click", () => { state.theme = state.theme === "dark" ? "light" : "dark"; applyTheme(); saveState(); });
  $("#load-more").addEventListener("click", () => { state.visibleCount += PAGE_SIZE; render(); });
  $("#export-settings").addEventListener("click", () => {
    const data = localStorage.getItem(STORAGE_KEY) || "{}";
    const url = URL.createObjectURL(new Blob([data], { type: "application/json" }));
    const link = make("a");
    link.href = url;
    link.download = "moaread-settings.json";
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  });
  $("#import-settings").addEventListener("change", async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    try {
      if (file.size > 1_000_000) throw new Error("파일이 너무 큽니다.");
      const imported = JSON.parse(await file.text());
      if (!imported || typeof imported !== "object" || Array.isArray(imported)) throw new Error("설정 파일 형식이 올바르지 않습니다.");
      localStorage.setItem(STORAGE_KEY, JSON.stringify(imported));
      window.location.reload();
    } catch (error) { showToast(error.message || "설정 파일을 읽지 못했습니다."); }
    event.target.value = "";
  });
}

async function init() {
  restoreState();
  bindEvents();
  $("#today-date").textContent = new Intl.DateTimeFormat("ko-KR", { year: "numeric", month: "short", day: "numeric", timeZone: "Asia/Seoul" }).format(new Date());
  try {
    const response = await fetch("./data/articles.json", { cache: "no-cache" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    if (!Array.isArray(data.articles) || !Array.isArray(data.sources)) throw new Error("피드 형식이 올바르지 않습니다.");
    state.articles = data.articles;
    state.sources = data.sources;
    state.generatedAt = data.generatedAt;
    $("#article-count").textContent = `${state.articles.length.toLocaleString("ko-KR")}개의 글 · ${state.sources.length}개 소스`;
    $("#updated-at").textContent = `마지막 갱신 ${formatDate(state.generatedAt)}`;
    renderSources();
    render();
  } catch (error) {
    $("#articles").replaceChildren(make("p", "load-error", "글을 불러오지 못했습니다. 잠시 후 다시 열어 주세요."));
    $("#article-count").textContent = "피드를 불러오지 못했습니다";
    $("#updated-at").textContent = "";
    console.error(error);
  }
}

init();
