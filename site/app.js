const STORAGE_KEY = "moaread-state-v1";
const PAGE_SIZE = 24;
const REPOSITORY_URL = "https://github.com/jwjp/technews";

const $ = (selector) => document.querySelector(selector);
const state = {
  articles: [],
  sources: [],
  generatedAt: null,
  candidates: [],
  candidateWeek: "",
  discoveryError: "",
  discoverySection: "tech",
  view: "reading",
  disabledSources: [],
  favoriteKeywords: "",
  hiddenKeywords: "",
  interestOnly: false,
  readIds: [],
  savedIds: [],
  savedArticles: [],
  sourceHealth: [],
  previousVisit: null,
  lastVisit: null,
  theme: "light",
  visibleCount: PAGE_SIZE,
  query: "",
  sort: "newest",
  newsTopic: "",
  economyBlogTopic: "",
  economyTopic: "",
};

function restoreState() {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
    if (Array.isArray(saved.savedArticles)) state.savedArticles = saved.savedArticles.filter(validSavedArticle);
    if (typeof saved.lastVisit === "string" && Number.isFinite(Date.parse(saved.lastVisit))) state.previousVisit = saved.lastVisit;
    for (const key of ["disabledSources", "readIds", "savedIds"]) {
      if (Array.isArray(saved[key])) state[key] = saved[key].filter((value) => typeof value === "string");
    }
    for (const key of ["favoriteKeywords", "hiddenKeywords", "theme", "newsTopic", "economyBlogTopic", "economyTopic", "sort"]) {
      if (typeof saved[key] === "string") state[key] = saved[key];
    }
  } catch {
    // A damaged browser setting should not prevent the feed from opening.
  }
  $("#sort-order").value = ["newest", "oldest", "balanced"].includes(state.sort) ? state.sort : "newest";
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
      savedArticles: state.savedArticles,
      lastVisit: state.lastVisit || state.previousVisit,
      theme: state.theme,
      sort: state.sort,
      newsTopic: state.newsTopic,
      economyBlogTopic: state.economyBlogTopic,
      economyTopic: state.economyTopic,
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

function subscriptionIssue(title, body) {
  const url = new URL(`${REPOSITORY_URL}/issues/new`);
  url.searchParams.set("title", title);
  url.searchParams.set("body", body);
  return url.href;
}

function keywords(value) {
  return value.split(",").map((word) => word.trim().toLocaleLowerCase("ko")).filter(Boolean);
}

function validSavedArticle(article) {
  return article && typeof article.id === "string" && typeof article.title === "string"
    && typeof article.url === "string" && /^https?:\/\//i.test(article.url)
    && typeof article.publishedAt === "string" && Number.isFinite(Date.parse(article.publishedAt))
    && typeof article.summary === "string"
    && (article.topics === undefined || (Array.isArray(article.topics) && article.topics.every((topic) => typeof topic === "string")))
    && Array.isArray(article.sourceIds)
    && article.sourceIds.every((id) => typeof id === "string");
}

function savedArticles() {
  const articles = new Map(state.savedArticles.map((article) => [article.id, article]));
  for (const article of state.articles) if (state.savedIds.includes(article.id)) articles.set(article.id, article);
  return [...articles.values()].filter((article) => state.savedIds.includes(article.id)).map((article) => ({
    ...article,
    sourceNames: Object.fromEntries(article.sourceIds.map((id) => [id, state.sources.find((source) => source.id === id)?.name || article.sourceNames?.[id] || "이전 구독 소스"]))
  }));
}

function matchesTopic(article, topic) {
  return topic === "기타" ? !(article.topics || []).length : (article.topics || []).includes(topic);
}

function hasSource(article) {
  return article.sourceIds.some((id) => !state.disabledSources.includes(id));
}

function hasSourceType(article, type) {
  return article.sourceIds.some((id) => !state.disabledSources.includes(id) && state.sources.find((source) => source.id === id)?.type === type);
}

function isTechBlog(article) {
  if (isEconomy(article) || isEconomyBlog(article)) return false;
  return article.sourceIds.some((id) => !state.disabledSources.includes(id) && !state.sources.find((source) => source.id === id)?.type);
}

function isNews(article) {
  return hasSourceType(article, "news");
}

function isEconomy(article) {
  return hasSourceType(article, "economy");
}

function isEconomyBlog(article) {
  return hasSourceType(article, "economy-blog");
}

function searchText(article) {
  const sourceNames = article.sourceIds.map((id) => state.sources.find((source) => source.id === id)?.name || "").join(" ");
  return `${article.title} ${article.summary} ${sourceNames} ${(article.topics || []).join(" ")}`.toLocaleLowerCase("ko");
}

function filteredArticles() {
  const excluded = keywords(state.hiddenKeywords);
  const favorites = keywords(state.favoriteKeywords);
  const query = state.query.trim().toLocaleLowerCase("ko");
  const result = (state.view === "saved" ? savedArticles() : state.articles).filter((article) => {
    if (state.view !== "saved" && !hasSource(article)) return false;
    if (state.view === "reading" && !isTechBlog(article)) return false;
    if (state.view === "news" && !isNews(article)) return false;
    if (["news", "reading"].includes(state.view) && state.newsTopic && !matchesTopic(article, state.newsTopic)) return false;
    if (state.view === "economy-blog" && !isEconomyBlog(article)) return false;
    if (state.view === "economy-blog" && state.economyBlogTopic && !matchesTopic(article, state.economyBlogTopic)) return false;
    if (state.view === "economy" && !isEconomy(article)) return false;
    if (state.view === "economy" && state.economyTopic && !matchesTopic(article, state.economyTopic)) return false;
    if (state.view === "new" && (!state.previousVisit || (article.firstSeenAt || article.publishedAt) <= state.previousVisit)) return false;
    if (state.view === "unread" && state.readIds.includes(article.id)) return false;
    if (state.view === "saved" && !state.savedIds.includes(article.id)) return false;
    const searchable = searchText(article);
    if (query && !searchable.includes(query)) return false;
    if (excluded.some((word) => searchable.includes(word))) return false;
    if (state.interestOnly && favorites.length && !favorites.some((word) => searchable.includes(word))) return false;
    return true;
  }).sort((a, b) => state.sort === "oldest" ? a.publishedAt.localeCompare(b.publishedAt) : b.publishedAt.localeCompare(a.publishedAt));
  if (state.sort !== "balanced") return result;
  const buckets = new Map();
  for (const article of result) {
    const key = article.sourceIds.find((id) => !state.disabledSources.includes(id));
    if (!buckets.has(key)) buckets.set(key, []);
    buckets.get(key).push(article);
  }
  const balanced = [];
  while (buckets.size) {
    for (const [key, articles] of buckets) {
      balanced.push(articles.shift());
      if (!articles.length) buckets.delete(key);
    }
  }
  return balanced;
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
      const row = make("div", "source-row");
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
      const unsubscribe = make("a", "source-unsubscribe", "구독 해지 ↗");
      unsubscribe.href = subscriptionIssue(`[구독 해제] ${source.name}`, `source_id: ${source.id}`);
      unsubscribe.target = "_blank";
      unsubscribe.rel = "noopener noreferrer";
      unsubscribe.title = `${source.name} 구독 해지 요청을 GitHub에서 작성`;
      row.append(label, unsubscribe);
      list.append(row);
    }
  }
}

function toggleId(key, id) {
  state[key] = state[key].includes(id) ? state[key].filter((item) => item !== id) : [...state[key], id];
  if (key === "savedIds") state.savedArticles = savedArticles();
  saveState();
  render();
  const replacement = document.querySelector(`[data-article-id="${CSS.escape(id)}"] .${key === "savedIds" ? "save-action" : "subtle-action"}`);
  (replacement || $("#view-title")).focus({ preventScroll: true });
}

function articleCard(article, index) {
  const card = make("article", `article-card${state.readIds.includes(article.id) ? " is-read" : ""}`);
  card.dataset.articleId = article.id;
  const ordinal = make("span", "article-ordinal", String(index + 1).padStart(2, "0"));
  const body = make("div", "article-body");
  const top = make("div", "article-top");
  const sources = make("div", "article-sources");
  for (const id of article.sourceIds) {
    const source = state.sources.find((item) => item.id === id);
    sources.append(make("span", "source-pill", source?.name || article.sourceNames?.[id] || "이전 구독 소스"));
  }
  if ((article.topics || []).length) {
    for (const topic of article.topics || []) sources.append(make("span", "topic-pill", topic));
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

function candidateInterest(candidate) {
  const words = keywords(state.favoriteKeywords);
  if (!words.length) return 0;
  const text = `${candidate.name} ${(candidate.topics || []).join(" ")} ${(candidate.samples || []).map((item) => item.title).join(" ")}`.toLocaleLowerCase("ko");
  return words.filter((word) => text.includes(word)).length;
}

function candidateCard(candidate) {
  const card = make("article", "candidate-card");
  const meta = make("div", "candidate-meta");
  meta.append(make("span", "candidate-kind", candidate.kind === "blog" ? "블로그" : candidate.kind === "policy" ? "정책 원문" : "뉴스"));
  for (const topic of (candidate.topics || []).slice(0, 4)) meta.append(make("span", "candidate-topic", topic));
  meta.append(make("time", "candidate-date", `최근 발행 ${formatDate(candidate.latestAt)}`));
  const title = make("h3", "candidate-title");
  const siteLink = make("a", "", candidate.name);
  siteLink.href = candidate.siteUrl;
  siteLink.target = "_blank";
  siteLink.rel = "noopener noreferrer";
  title.append(siteLink);
  const detail = make("p", "candidate-detail", `최근 120일 ${candidate.recentCount}개 글 · ${candidate.foundVia}에서 발견`);
  const sampleLabel = make("div", "candidate-sample-label", "최근 글 미리보기");
  const samples = make("ul", "candidate-samples");
  for (const sample of candidate.samples || []) {
    const item = make("li");
    const link = make("a", "", sample.title);
    link.href = sample.url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    item.append(link);
    samples.append(item);
  }
  const actions = make("div", "candidate-actions");
  const subscribed = state.sources.find((source) => source.id === `candidate-${candidate.id}` || source.url === candidate.feedUrl);
  const subscribe = make("a", "candidate-action", subscribed ? "구독 해지 ↗" : "구독 신청 ↗");
  subscribe.href = subscribed
    ? subscriptionIssue(`[구독 해제] ${subscribed.name}`, `source_id: ${subscribed.id}`)
    : subscriptionIssue(`[구독] ${candidate.name}`, `candidate_id: ${candidate.id}`);
  subscribe.target = "_blank";
  subscribe.rel = "noopener noreferrer";
  actions.append(subscribe);
  card.append(meta, title, detail, sampleLabel, samples, actions);
  return card;
}

function renderDiscovery() {
  document.querySelectorAll(".discover-tab").forEach((button) => {
    const active = button.dataset.discoverSection === state.discoverySection;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
  });
  const week = state.candidateWeek.match(/^(\d{4})-W(\d{2})$/);
  $("#discover-week").textContent = week ? `${week[1]}년 ${Number(week[2])}주차 추천` : "주간 후보";
  const list = $("#discover-list");
  list.replaceChildren();
  if (state.discoveryError) {
    list.append(make("p", "discover-empty", state.discoveryError));
    $("#result-count").textContent = "—";
    return;
  }
  const candidates = state.candidates.filter((candidate) => candidate.section === state.discoverySection);
  candidates.sort((a, b) => {
    return candidateInterest(b) - candidateInterest(a) || b.score - a.score;
  });
  $("#result-count").textContent = `${candidates.length}개 소스`;
  if (!candidates.length) {
    list.append(make("p", "discover-empty", "이번 주에 조건을 통과한 새 후보가 없습니다."));
    return;
  }
  candidates.forEach((candidate) => list.append(candidateCard(candidate)));
}

function render() {
  const titles = {
    reading: ["기술 글", "새로 올라온 기술 블로그와 커뮤니티 글을 둘러보세요."],
    news: ["기술 뉴스", "기술·개발·소프트웨어·보안·AI·자동차 뉴스를 골라 보세요."],
    "economy-blog": ["경제 글", "주식·경제·부동산을 다루는 블로그 글을 모았어요."],
    economy: ["경제 뉴스", "주식·금융·부동산·경제·정책 소식을 골라 보세요."],
    all: ["전체 글", "기술·경제 블로그와 뉴스를 시간순으로 모았어요."],
    unread: ["읽지 않은 글", "아직 만나지 않은 글을 모았어요."],
    new: ["새로 들어온 글", state.previousVisit ? "지난 방문 이후 수집된 글입니다." : "첫 방문입니다. 다음 방문부터 새 글을 모아 보여드려요."],
    saved: ["저장한 글", "다시 읽고 싶은 글을 모았어요."],
    discover: ["새 소스 발견", "기술·경제 RSS를 매주 살펴보고 새 구독 후보를 추천해요."],
  };
  $("#view-title").textContent = titles[state.view][0];
  $("#view-description").textContent = titles[state.view][1];
  document.querySelectorAll(".nav-item").forEach((item) => { item.classList.toggle("active", item.dataset.view === state.view); item.setAttribute("aria-current", item.dataset.view === state.view ? "page" : "false"); });
  $("#news-topics").hidden = !["news", "reading"].includes(state.view);
  $("#economy-blog-topics").hidden = state.view !== "economy-blog";
  $("#economy-topics").hidden = state.view !== "economy";
  const discovering = state.view === "discover";
  $("#article-toolbar").hidden = discovering;
  $("#discover-panel").hidden = !discovering;
  $("#articles").hidden = discovering;
  for (const [selector, selected] of [["#news-topics", state.newsTopic], ["#economy-blog-topics", state.economyBlogTopic], ["#economy-topics", state.economyTopic]]) {
    document.querySelectorAll(`${selector} .topic-button`).forEach((button) => {
      const active = button.dataset.topic === selected;
      button.classList.toggle("active", active);
      button.setAttribute("aria-pressed", String(active));
    });
  }
  const available = state.articles.filter(hasSource);
  $("#count-reading").textContent = available.filter(isTechBlog).length.toLocaleString("ko-KR");
  $("#count-news").textContent = available.filter(isNews).length.toLocaleString("ko-KR");
  $("#count-economy-blog").textContent = available.filter(isEconomyBlog).length.toLocaleString("ko-KR");
  $("#count-economy").textContent = available.filter(isEconomy).length.toLocaleString("ko-KR");
  $("#count-all").textContent = available.length.toLocaleString("ko-KR");
  $("#count-unread").textContent = available.filter((item) => !state.readIds.includes(item.id)).length.toLocaleString("ko-KR");
  $("#count-saved").textContent = savedArticles().length.toLocaleString("ko-KR");
  $("#count-new").textContent = available.filter((article) => state.previousVisit && (article.firstSeenAt || article.publishedAt) > state.previousVisit).length.toLocaleString("ko-KR");
  $("#count-discover").textContent = state.candidates.length.toLocaleString("ko-KR");
  if (discovering) {
    $("#filter-summary").hidden = true;
    $("#load-more").hidden = true;
    renderDiscovery();
    return;
  }
  const articles = filteredArticles();
  $("#result-count").textContent = `${articles.length.toLocaleString("ko-KR")}개의 글`;
  const summary = $("#filter-summary");
  const filters = [];
  if (state.query.trim()) filters.push(`검색: ${state.query.trim()}`);
  if (["news", "reading"].includes(state.view) && state.newsTopic) filters.push(`분야: ${state.newsTopic}`);
  if (state.view === "economy-blog" && state.economyBlogTopic) filters.push(`분야: ${state.economyBlogTopic}`);
  if (state.view === "economy" && state.economyTopic) filters.push(`분야: ${state.economyTopic}`);
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
    appendArticleBatch(articles, 0, state.visibleCount);
  }
  $("#load-more").hidden = articles.length <= state.visibleCount;
}

function appendArticleBatch(articles, start, end) {
  const container = $("#articles");
  for (let index = start; index < Math.min(end, articles.length); index++) {
    if (index > 0 && index % PAGE_SIZE === 0) {
      const marker = make("p", "article-batch-marker", `이어서 보기 · ${index + 1}~${Math.min(index + PAGE_SIZE, articles.length)}번째 글`);
      marker.dataset.batchStart = String(index);
      marker.tabIndex = -1;
      container.append(marker);
    }
    container.append(articleCard(articles[index], index));
  }
}

function loadMoreArticles(event) {
  const articles = filteredArticles();
  const start = state.visibleCount;
  if (start >= articles.length) return;
  const top = window.scrollY;
  const left = window.scrollX;
  state.visibleCount = Math.min(start + PAGE_SIZE, articles.length);
  appendArticleBatch(articles, start, state.visibleCount);
  $("#load-more").hidden = state.visibleCount >= articles.length;
  // Move keyboard focus into the new batch without moving the viewport.
  if (event.detail === 0 || $("#load-more").hidden) {
    $("#articles").querySelector(`[data-batch-start="${start}"]`)?.focus({ preventScroll: true });
  }
  window.scrollTo({ top, left, behavior: "instant" });
  requestAnimationFrame(() => window.scrollTo({ top, left, behavior: "instant" }));
}

function bindEvents() {
  document.querySelectorAll(".nav-item").forEach((item) => item.addEventListener("click", () => {
    state.view = item.dataset.view;
    state.visibleCount = PAGE_SIZE;
    render();
    $("#main-content").scrollIntoView({ behavior: "smooth", block: "start" });
  }));
  document.querySelectorAll(".topic-button").forEach((button) => button.addEventListener("click", () => {
    const topicKey = button.closest("#economy-blog-topics") ? "economyBlogTopic" : button.closest("#economy-topics") ? "economyTopic" : "newsTopic";
    state[topicKey] = button.dataset.topic;
    state.visibleCount = PAGE_SIZE;
    saveState();
    render();
  }));
  document.querySelectorAll(".discover-tab").forEach((button) => button.addEventListener("click", () => {
    state.discoverySection = button.dataset.discoverSection;
    renderDiscovery();
  }));
  $("#search-input").addEventListener("input", (event) => { state.query = event.target.value; state.visibleCount = PAGE_SIZE; render(); });
  $("#sort-order").addEventListener("change", (event) => { state.sort = event.target.value; state.visibleCount = PAGE_SIZE; saveState(); render(); });
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
  $("#load-more").addEventListener("click", loadMoreArticles);
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
      if (file.size > 20_000_000) throw new Error("파일이 너무 큽니다.");
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
    state.sourceHealth = data.sourceHealth || [];
    state.lastVisit = new Date().toISOString();
    state.savedArticles = savedArticles().map((article) => ({ ...article, sourceNames: Object.fromEntries(article.sourceIds.map((id) => [id, state.sources.find((source) => source.id === id)?.name || article.sourceNames?.[id] || "이전 구독 소스"])) }));
    saveState();
    const status = $("#collection-status");
    status.replaceChildren();
    for (const health of state.sourceHealth.filter((source) => !source.ok)) {
      const name = state.sources.find((source) => source.id === health.id)?.name || health.id;
      status.append(make("p", "field-help", `${name}: ${health.error || "수집 실패"} · 마지막 성공 ${health.lastSuccessAt ? formatDate(health.lastSuccessAt) : "기록 없음"}`));
    }
    if (!status.children.length) status.append(make("p", "field-help", "모든 소스를 정상적으로 확인했습니다."));
    for (const metric of data.retentionStats || []) {
      const name = state.sources.find((source) => source.id === metric.id)?.name || metric.id;
      status.append(make("p", "field-help", `${name}: ${metric.kept}개 보관 · 이번 수집에서 ${metric.excluded}개 제외${metric.oldestAt ? ` · 가장 오래된 글 ${formatDate(metric.oldestAt)}` : ""}`));
    }
    state.generatedAt = data.generatedAt;
    $("#article-count").textContent = `${state.articles.length.toLocaleString("ko-KR")}개의 글 · ${state.sources.length}개 소스`;
    $("#updated-at").textContent = `확인 ${new Intl.DateTimeFormat("ko-KR", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit", timeZone: "Asia/Seoul" }).format(new Date(state.generatedAt))} · ${data.sourceHealth ? `${data.sourceHealth.filter((source) => source.ok).length}/${data.sources.length}개 소스 정상` : "수집 상태 확인 중"}`;
    renderSources();
    render();
  } catch (error) {
    $("#articles").replaceChildren(make("p", "load-error", "글을 불러오지 못했습니다. 잠시 후 다시 열어 주세요."));
    $("#article-count").textContent = "피드를 불러오지 못했습니다";
    $("#updated-at").textContent = "";
    console.error(error);
  }
  try {
    const response = await fetch("./data/candidates.json", { cache: "no-cache" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    if (!Array.isArray(data.candidates)) throw new Error("후보 형식이 올바르지 않습니다.");
    state.candidates = data.candidates;
    state.candidateWeek = data.week || "";
  } catch (error) {
    state.discoveryError = "추천 후보를 불러오지 못했습니다. 잠시 후 다시 열어 주세요.";
    console.error(error);
  }
  render();
}

init();
