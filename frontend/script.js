const BACKEND_URL = window.DIGICOUNSELLOR_BACKEND_URL || 'http://localhost:8000';
const PROFILE_KEY = 'digicounsellor.profile.v1';
const FAST_MODE_KEY = 'digicounsellor.fastDemoMode.v1';

const $ = (selector) => document.querySelector(selector);

const form = $('#profileForm');
const saveBtn = $('#saveProfileBtn');
const clearProfileBtn = $('#clearProfileBtn');
const profileState = $('#profileState');
const profileNotice = $('#profileNotice');
const activeProfileSummary = $('#activeProfileSummary');
const eduSystem = $('#educationSystem');
const matricFields = $('#matricFields');
const olevelFields = $('#olevelFields');
const chatBox = $('#chatBox');
const chatForm = $('#chatForm');
const userInput = $('#userInput');
const sendBtn = $('#sendBtn');
const statusDot = $('#statusDot');
const chatStatusText = $('#chatStatusText');
const backendState = $('#backendState');
const runtimeBanner = $('#runtimeBanner');
const providerBadge = $('#providerBadge');
const selectedUniversityBar = $('#selectedUniversityBar');
const selectedUniversityName = $('#selectedUniversityName');
const clearSelectedBtn = $('#clearSelectedBtn');
const fastModeToggle = $('#fastModeToggle');

let studentProfile = null;
let selectedUniversity = null;
let typingEl = null;
let typingTimer = null;
let backendOnline = false;
let isBusy = false;
let restoringProfile = false;
let fastDemoMode = localStorage.getItem(FAST_MODE_KEY) !== 'false';
let lastRecommendationData = null;

const loadingStatusLines = [
  'Searching university data',
  'Checking your profile',
  'Ranking suitable universities',
  'Asking local AI for a short explanation',
];

const recommendStatusLines = [
  'Searching university data',
  'Checking your profile',
  'Ranking suitable universities',
];

const gradePercentages = {
  'A*': 95,
  A: 90,
  B: 80,
  C: 70,
  D: 60,
  E: 50,
};

function escapeHtml(value = '') {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function isValidLink(url) {
  if (!url || typeof url !== 'string') return false;
  const trimmed = url.trim();
  if (!trimmed) return false;
  if (trimmed === '#') return false;
  if (trimmed.toLowerCase().startsWith('todo')) return false;
  if (trimmed.toLowerCase().includes('placeholder')) return false;
  if (!trimmed.startsWith('http://') && !trimmed.startsWith('https://')) return false;
  return true;
}

function formatMarkdown(text = '') {
  return escapeHtml(text)
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br>');
}

function normalizeFieldLabel(value = '') {
  if (value === 'CS') return 'Computer Science';
  if (value === 'SE') return 'Software Engineering';
  return value || 'Computer Science';
}

function setEducationFields(system) {
  const isOLevel = system === 'olevel';
  matricFields.classList.toggle('hidden', isOLevel);
  olevelFields.classList.toggle('hidden', !isOLevel);
  document.getElementById('matricMarks').required = !isOLevel;
  document.getElementById('interMarks').required = !isOLevel;
}

function showProfileNotice(message, type = 'success') {
  profileNotice.textContent = message;
  profileNotice.className = `form-notice show ${type}`;
}

function hideProfileNotice() {
  profileNotice.textContent = '';
  profileNotice.className = 'form-notice';
}

function setProfileState(state, text) {
  profileState.className = `state-pill ${state || ''}`.trim();
  profileState.textContent = text;
}

function getFieldValue(id) {
  const node = document.getElementById(id);
  return node ? node.value.trim() : '';
}

function parsePercentage(value, label) {
  if (!value) {
    return { ok: false, message: `${label} is required.` };
  }
  const num = Number.parseFloat(value);
  if (Number.isNaN(num) || num < 0 || num > 100) {
    return { ok: false, message: `${label} must be between 0 and 100.` };
  }
  return { ok: true, value: num };
}

function gradeToPct(grade) {
  return gradePercentages[grade] || 0;
}

const GREETINGS = new Set([
  'hey', 'hello', 'hi', 'salam', 'assalam', 'alaikum',
  'thanks', 'thank you', 'thankyou', 'ok', 'okay',
  'yes', 'no', 'thx',
]);

const REC_PHRASES = [
  'best for me', 'recommend', 'best match', 'safe option',
  'universities in', 'cs in', 'se in', 'options for me',
  'show me option', 'which universit',
  'suitable for me', 'good for me', 'suggest',
  'apply to',
];

const UNI_NAMES = [
  'fast', 'lums', 'nust', 'pims', 'giki', 'habib', 'itu',
  'ned', 'comsats', 'bahria', 'iqra', 'szabist',
  'uet', 'lse', 'punjab university', 'karachi university',
  'nca', 'beaconhouse', 'air university', 'qau', 'ucp',
  'virtual university', 'ist', 'pieas', 'iba',
];

const FOLLOW_UP_PHRASES = [
  'tell me about', 'tell me more', 'check eligibility',
  'fees for', 'admission requirement', 'admission link',
  'what should i do next', 'how to apply', 'entry test',
  'deadline', 'requirements for', 'compare',
];

const INFO_PHRASES = {
  fee: ['fee', 'fees', 'fee structure', 'cost', 'tuition', 'semester fee', 'total fee'],
  eligibility: ['eligibility', 'eligible', 'requirements', 'criteria', 'minimum marks', 'am i eligible'],
  entry_test: ['entry test', 'test', 'nts', 'nat', 'ecat', 'net', 'admission test', 'entry requirement'],
  deadline: ['deadline', 'last date', 'dates', 'schedule', 'closing date'],
  admission_links: ['admission link', 'apply', 'application', 'portal', 'admission page', 'how to apply'],
};

const INFO_KEYS = Object.keys(INFO_PHRASES);

function detectIntent(question) {
  if (!question) return 'unknown';
  const lower = question.toLowerCase().trim();
  const cleaned = lower.replace(/[.!?,]+$/, '').trim();
  if (GREETINGS.has(cleaned)) return 'greeting';
  const hasUni = UNI_NAMES.some((name) => lower.includes(name));
  const isFollowUp = FOLLOW_UP_PHRASES.some((phrase) => lower.includes(phrase));
  const isRec = REC_PHRASES.some((phrase) => lower.includes(phrase));
  if (isRec) return 'recommendation';
  if (isFollowUp && hasUni) return 'university_info';
  if (isFollowUp) return 'follow_up';
  if (hasUni) {
    const hasInfo = INFO_KEYS.some((key) =>
      INFO_PHRASES[key].some((phrase) => lower.includes(phrase))
    );
    if (hasInfo) return 'university_info';
    return 'university_specific';
  }
  if (cleaned.length < 10) return 'greeting';
  return 'follow_up';
}

function collectProfile() {
  const name = getFieldValue('studentName');
  const system = eduSystem.value;
  const preferredField = getFieldValue('preferredField');

  if (!name) {
    return { ok: false, message: 'Please enter the student name.' };
  }
  if (!preferredField) {
    return { ok: false, message: 'Please select Computer Science or Software Engineering.' };
  }

  let matricPct = 0;
  let interPct = 0;
  const profile = {
    name,
    education_system: system,
    preferred_field: normalizeFieldLabel(preferredField),
    city_preference: getFieldValue('cityPref') || 'Any city',
    budget: getFieldValue('budget'),
    entry_test: getFieldValue('entryTest'),
    university_type: getFieldValue('universityType') || 'either',
    matric_marks: '',
    inter_marks: '',
    matric_percentage: '',
    intermediate_percentage: '',
    o_level_equivalence: '',
    a_level_equivalence: '',
    o_level_grade: '',
    a_level_grade: '',
  };

  if (system === 'olevel') {
    const oEquiv = getFieldValue('olevelEquivalence');
    const aEquiv = getFieldValue('alevelEquivalence');
    const oGrade = getFieldValue('olevelGrade');
    const aGrade = getFieldValue('alevelGrade');

    if (!oEquiv && !oGrade) {
      return { ok: false, message: 'Please add O Level equivalence or an average O Level grade.' };
    }
    if (!aEquiv && !aGrade) {
      return { ok: false, message: 'Please add A Level equivalence or an average A Level grade.' };
    }

    if (oEquiv) {
      const parsed = parsePercentage(oEquiv, 'O Level equivalence');
      if (!parsed.ok) return parsed;
      matricPct = parsed.value;
    } else {
      matricPct = gradeToPct(oGrade);
    }

    if (aEquiv) {
      const parsed = parsePercentage(aEquiv, 'A Level equivalence');
      if (!parsed.ok) return parsed;
      interPct = parsed.value;
    } else {
      interPct = gradeToPct(aGrade);
    }

    profile.o_level_equivalence = oEquiv;
    profile.a_level_equivalence = aEquiv;
    profile.o_level_grade = oGrade;
    profile.a_level_grade = aGrade;
  } else {
    const matric = parsePercentage(getFieldValue('matricMarks'), 'Matric percentage');
    if (!matric.ok) return matric;
    const inter = parsePercentage(getFieldValue('interMarks'), 'Intermediate percentage');
    if (!inter.ok) return inter;
    matricPct = matric.value;
    interPct = inter.value;
  }

  profile.matric_marks = String(matricPct);
  profile.inter_marks = String(interPct);
  profile.matric_percentage = String(matricPct);
  profile.intermediate_percentage = String(interPct);
  return { ok: true, profile };
}

function populateProfileForm(profile) {
  restoringProfile = true;
  $('#studentName').value = profile.name || '';
  eduSystem.value = profile.education_system === 'olevel' ? 'olevel' : 'matric_inter';
  setEducationFields(eduSystem.value);
  $('#matricMarks').value = profile.matric_marks || profile.matric_percentage || '';
  $('#interMarks').value = profile.inter_marks || profile.intermediate_percentage || '';
  $('#olevelEquivalence').value = profile.o_level_equivalence || '';
  $('#alevelEquivalence').value = profile.a_level_equivalence || '';
  $('#olevelGrade').value = profile.o_level_grade || '';
  $('#alevelGrade').value = profile.a_level_grade || '';
  $('#preferredField').value = normalizeFieldLabel(profile.preferred_field || '');
  $('#cityPref').value = profile.city_preference || 'Any city';
  $('#budget').value = profile.budget || '';
  $('#entryTest').value = profile.entry_test || '';
  $('#universityType').value = profile.university_type || 'either';
  restoringProfile = false;
}

function renderActiveProfile(profile) {
  const city = profile.city_preference || 'Any city';
  const typeLabel = profile.university_type === 'public'
    ? 'Public preferred'
    : profile.university_type === 'private'
      ? 'Private preferred'
      : 'Public or private';
  const isOLevel = profile.education_system === 'olevel';
  const levelLabel1 = isOLevel ? 'O Level' : 'Matric';
  const levelLabel2 = isOLevel ? 'A Level' : 'Inter';
  activeProfileSummary.hidden = false;
  activeProfileSummary.innerHTML = `
    <strong>Using saved profile</strong>
    ${escapeHtml(profile.name)} · ${escapeHtml(profile.preferred_field)} · ${escapeHtml(city)}<br>
    ${levelLabel1} ${escapeHtml(profile.matric_marks)}% · ${levelLabel2} ${escapeHtml(profile.inter_marks)}% · ${escapeHtml(typeLabel)}
  `;
}

function enableChat() {
  userInput.disabled = false;
  sendBtn.disabled = isBusy;
  userInput.placeholder = 'Ask about universities, eligibility, fees, or next steps';
  updateChatStatus();
}

function disableChat() {
  userInput.disabled = true;
  sendBtn.disabled = true;
  userInput.placeholder = 'Save your profile to start asking questions';
  updateChatStatus();
}

function updateChatStatus() {
  statusDot.classList.remove('online', 'offline');
  if (!backendOnline) {
    statusDot.classList.add('offline');
    chatStatusText.textContent = 'Backend offline';
    return;
  }
  if (!studentProfile) {
    chatStatusText.textContent = 'Profile needed';
    return;
  }
  statusDot.classList.add('online');
  chatStatusText.textContent = isBusy ? 'Thinking' : 'Ready';
}

function saveProfile() {
  const result = collectProfile();
  if (!result.ok) {
    showProfileNotice(result.message, 'error');
    return;
  }

  studentProfile = result.profile;
  localStorage.setItem(PROFILE_KEY, JSON.stringify(studentProfile));
  setProfileState('saved', 'Saved');
  saveBtn.textContent = 'Update profile';
  renderActiveProfile(studentProfile);
  enableChat();
  showProfileNotice('Profile saved. New questions will use these details.', 'success');
}

function clearProfile() {
  localStorage.removeItem(PROFILE_KEY);
  studentProfile = null;
  selectedUniversity = null;
  lastRecommendationData = null;
  const existingRecBlock = chatBox.querySelector('.split-response-block');
  if (existingRecBlock) existingRecBlock.remove();
  resetProfileForm();
  setEducationFields(eduSystem.value);
  setProfileState('', 'Not saved');
  saveBtn.textContent = 'Save profile';
  activeProfileSummary.hidden = true;
  selectedUniversityBar.classList.add('hidden');
  disableChat();
  hideProfileNotice();
}

function resetProfileForm() {
  form.reset();
  [
    'studentName', 'matricMarks', 'interMarks', 'olevelEquivalence',
    'alevelEquivalence', 'olevelGrade', 'alevelGrade', 'preferredField',
    'budget', 'entryTest'
  ].forEach((id) => {
    const node = document.getElementById(id);
    if (node) node.value = '';
  });
  eduSystem.value = 'matric_inter';
  $('#cityPref').value = 'Any city';
  $('#universityType').value = 'either';
}

function markProfileDirty() {
  if (restoringProfile || !studentProfile) return;
  setProfileState('unsaved', 'Unsaved edits');
  saveBtn.textContent = 'Update profile';
  showProfileNotice('You have unsaved profile edits. Press Update profile before the next answer.', 'success');
}

async function refreshBackendStatus() {
  setBackendStatus('checking', 'Checking backend', 'Connecting to the local counselling backend.');
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), 3500);
  try {
    const response = await fetch(`${BACKEND_URL}/health`, { signal: controller.signal });
    window.clearTimeout(timer);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const health = await response.json();
    backendOnline = true;
    const providerText = health.ollama
      ? 'Local AI connected'
      : health.lm_studio
        ? 'LM Studio ready'
        : 'Fast data mode ready';
    setBackendStatus(
      'online',
      'Backend connected',
      `Backend connected · ${health.chroma_docs || 0} RAG documents · ${providerText}`
    );
  } catch (error) {
    window.clearTimeout(timer);
    backendOnline = false;
    const isRemoteFrontend = !['localhost', '127.0.0.1', ''].includes(window.location.hostname);
    const message = isRemoteFrontend
      ? 'Frontend loaded. Start the local backend on port 8000 for live counselling.'
      : 'Start the FastAPI backend on http://localhost:8000 for live counselling.';
    setBackendStatus('offline', 'Backend offline', message);
  }
  updateChatStatus();
}

function setBackendStatus(state, label, detail) {
  backendState.className = `connection-pill ${state === 'checking' ? '' : state}`;
  backendState.textContent = label;
  runtimeBanner.className = `runtime-banner ${state === 'checking' ? '' : state}`;
  runtimeBanner.textContent = detail;
}

function providerLabel(provider, model) {
  if (provider === 'data') return 'Data recommendations ready';
  if (provider === 'ollama') return 'Local AI connected';
  if (provider === 'lm_studio') return 'LM Studio connected';
  if (provider === 'fallback' || provider === 'fallback_after_incomplete') return 'Fast data mode';
  return model ? `${provider || 'Provider'} · ${model}` : (provider || 'Provider');
}

function updateProviderBadge(data) {
  providerBadge.textContent = providerLabel(data.provider_used, data.selected_model);
}

function createMessage(sender, html, extraClass = '') {
  const article = document.createElement('article');
  article.className = `message ${sender} ${extraClass}`.trim();
  if (sender !== 'user' && sender !== 'system') {
    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    avatar.setAttribute('aria-hidden', 'true');
    avatar.textContent = 'DC';
    article.appendChild(avatar);
  }
  const body = document.createElement('div');
  body.className = 'message-body';
  body.innerHTML = html;
  article.appendChild(body);
  return article;
}

function addUserMessage(text) {
  const el = createMessage('user', escapeHtml(text));
  chatBox.appendChild(el);
  scrollToElement(el);
}

function addSystemMessage(text, type = '') {
  const el = createMessage('system', escapeHtml(text), type);
  chatBox.appendChild(el);
  scrollToElement(el);
}

function showTyping(lines = loadingStatusLines) {
  hideTyping();
  let statusIndex = 0;
  const activeLines = lines.length ? lines : loadingStatusLines;
  typingEl = createMessage(
    'bot',
    `<span class="typing-progress" aria-live="polite">
      <span class="typing-status">${activeLines[statusIndex]}</span>
      <span class="typing-dots" aria-label="DigiCounsellor is working"><span></span><span></span><span></span></span>
    </span>`
  );
  chatBox.appendChild(typingEl);
  const statusNode = typingEl.querySelector('.typing-status');
  typingTimer = window.setInterval(() => {
    statusIndex = (statusIndex + 1) % activeLines.length;
    if (statusNode) statusNode.textContent = activeLines[statusIndex];
  }, 1400);
  scrollToElement(typingEl);
}

function hideTyping() {
  if (typingTimer) {
    window.clearInterval(typingTimer);
    typingTimer = null;
  }
  if (typingEl) {
    typingEl.remove();
    typingEl = null;
  }
}

function scrollToElement(el) {
  if (!el) return;
  el.scrollIntoView({ behavior: "smooth", block: "start" });
}

function scrollChatToBottom() {
  chatBox.scrollTop = chatBox.scrollHeight;
}

function fitClass(fit = '') {
  const value = fit.toLowerCase();
  if (value.includes('not eligible')) return 'fit-not-eligible';
  if (value.includes('best')) return 'fit-best';
  if (value.includes('safe')) return 'fit-safe';
  if (value.includes('difficult')) return 'fit-difficult';
  return 'fit-backup';
}

function renderRecommendationCard(rec) {
  const card = document.createElement('article');
  card.className = 'recommendation-card';
  const fields = (rec.fields || []).slice(0, 3).join(', ');
  const validLinks = (rec.admission_links || []).filter((link) => isValidLink(link.url)).slice(0, 3);
  card.innerHTML = `
    <div class="card-top">
      <div>
        <h3 class="university-title">${escapeHtml(rec.short_name || rec.university_name)}</h3>
        <div class="university-meta">
          <span class="meta-chip">${escapeHtml(rec.city || 'Pakistan')}</span>
          <span class="meta-chip">${escapeHtml(rec.university_type || 'University')}</span>
          <span class="meta-chip">${escapeHtml(rec.tier_label || 'Option')}</span>
        </div>
      </div>
      <span class="fit-badge ${fitClass(rec.fit_level)}">${escapeHtml(rec.fit_level || 'Option')}</span>
    </div>
    <p class="card-copy">${escapeHtml(rec.match_reason || 'Relevant option from the university data.')}</p>
    <ul class="card-detail-list">
      <li><strong>Fields:</strong> ${escapeHtml(fields || 'CS / SE details need verification')}</li>
      <li><strong>Eligibility:</strong> ${escapeHtml(rec.eligibility_summary || 'Check official eligibility criteria')}</li>
      <li><strong>Test:</strong> ${escapeHtml(rec.entry_test || 'Check official policy')}</li>
      <li><strong>Fees:</strong> ${escapeHtml(rec.fee_summary || 'Verify latest official fee page')}</li>
    </ul>
    ${validLinks.length ? `
    <div class="link-row">
      ${validLinks.map((link) => `
        <a class="link-action" href="${escapeHtml(link.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(link.label || 'Official link')}</a>
      `).join('')}
    </div>` : ''}
    <div class="card-actions">
      <button type="button" class="mini-action" data-action="focus">Select</button>
      <button type="button" class="mini-action" data-action="eligibility">Eligibility</button>
      <button type="button" class="mini-action" data-action="fees">Fees</button>
      <button type="button" class="mini-action" data-action="compare">Compare</button>
    </div>
  `;

  card.querySelector('[data-action="focus"]').addEventListener('click', () => {
    setSelectedUniversity(rec);
    addSystemMessage(`${rec.short_name || rec.university_name} is now the focused university.`);
  });
  card.querySelector('[data-action="eligibility"]').addEventListener('click', () => {
    sendFollowUp(`Check my eligibility for ${rec.short_name || rec.university_name}.`, rec);
  });
  card.querySelector('[data-action="fees"]').addEventListener('click', () => {
    sendFollowUp(`Show fee info and official admission links for ${rec.short_name || rec.university_name}.`, rec);
  });
  card.querySelector('[data-action="compare"]').addEventListener('click', () => {
    sendFollowUp(`Help me compare ${rec.short_name || rec.university_name} with my other suitable options.`, rec);
  });
  return card;
}

function renderRecommendations(recommendations = [], heading = 'Recommended universities') {
  if (!recommendations.length) return null;
  const section = document.createElement('section');
  section.className = 'recommendation-set';
  const title = document.createElement('h3');
  title.className = 'recommendation-heading';
  title.textContent = heading;
  const grid = document.createElement('div');
  grid.className = 'recommendation-grid';
  recommendations.slice(0, 6).forEach((rec) => grid.appendChild(renderRecommendationCard(rec)));
  section.append(title, grid);
  return section;
}

function renderNextSteps(steps = [], recommendations = []) {
  const section = document.createElement('section');
  section.className = 'next-steps';
  const actionSource = selectedUniversity || recommendations[0];
  const quickActions = actionSource ? `
    <div class="followup-actions">
      <button type="button" class="mini-action" data-follow="details">Tell me more</button>
      <button type="button" class="mini-action" data-follow="requirements">Admission requirements</button>
      <button type="button" class="mini-action" data-follow="next">What should I do next?</button>
    </div>
  ` : '';
  section.innerHTML = `
    <h3 class="next-step-heading">Next moves</h3>
    <ol>
      ${(steps.length ? steps : ['Open official admission pages.', 'Prepare for entry tests.', 'Compare one safe and one target option.'])
        .map((step) => `<li>${escapeHtml(step)}</li>`).join('')}
    </ol>
    ${quickActions}
  `;
  if (actionSource) {
    section.querySelector('[data-follow="details"]').addEventListener('click', () => {
      sendFollowUp(`Tell me more about ${actionSource.short_name || actionSource.university_name}.`, actionSource);
    });
    section.querySelector('[data-follow="requirements"]').addEventListener('click', () => {
      sendFollowUp(`Show admission requirements for ${actionSource.short_name || actionSource.university_name}.`, actionSource);
    });
    section.querySelector('[data-follow="next"]').addEventListener('click', () => {
      sendFollowUp(`What should I do next for ${actionSource.short_name || actionSource.university_name}?`, actionSource);
    });
  }
  return section;
}

function renderSources(sources = []) {
  if (!sources.length) return null;
  const details = document.createElement('details');
  details.className = 'sources-panel';
  details.innerHTML = `
    <summary>Sources used (${sources.length})</summary>
    <div class="source-list">
      ${sources.map((source) => {
        const url = (source.source_url || '').split(';')[0];
        const validUrl = isValidLink(url) ? url : '';
        return `
          <div class="source-item">
            <strong>${escapeHtml(source.university_name || 'University source')}</strong>
            ${validUrl ? `<a href="${escapeHtml(validUrl)}" target="_blank" rel="noopener noreferrer">${escapeHtml(validUrl)}</a>` : ''}
            <span>${escapeHtml((source.preview || '').slice(0, 180))}</span>
          </div>
        `;
      }).join('')}
    </div>
  `;
  return details;
}

function activeSelectedUniversityId() {
  return selectedUniversity ? selectedUniversity.university_id : '';
}

function requestPayload(question, selectedId = activeSelectedUniversityId()) {
  return {
    profile: studentProfile,
    question,
    selected_university: selectedId || '',
  };
}

function setSummaryMessage(summaryBody, text, type = 'pending') {
  if (!summaryBody) return;
  summaryBody.innerHTML = `<div class="answer-content summary-${type}">${formatMarkdown(text)}</div>`;
}

function addRecommendationTurn(data) {
  updateProviderBadge({ provider_used: 'data', selected_model: '' });
  const existingBlock = chatBox.querySelector('.split-response-block');
  if (existingBlock) existingBlock.remove();
  const block = document.createElement('section');
  block.className = 'response-block split-response-block';

  const summaryMessage = createMessage(
    'bot',
    '<div class="answer-content summary-pending"><strong>Recommendations are ready.</strong><br>Writing a short AI summary...</div>',
    'summary-pending'
  );
  block.appendChild(summaryMessage);

  const recommendations = data.recommended_universities || [];
  const safeOptions = data.safe_options || [];
  const difficultOptions = data.difficult_options || [];
  const notEligible = data.not_eligible_options || [];

  let hasAnyCards = false;
  const recSection = renderRecommendations(recommendations, 'Best matches');
  if (recSection) { block.appendChild(recSection); hasAnyCards = true; }
  const safeSection = renderRecommendations(safeOptions, 'Safe options');
  if (safeSection) { block.appendChild(safeSection); hasAnyCards = true; }
  const diffSection = renderRecommendations(difficultOptions, 'Difficult but possible');
  if (diffSection) { block.appendChild(diffSection); hasAnyCards = true; }
  const notEligibleSection = renderRecommendations(notEligible, 'Not eligible right now');
  if (notEligibleSection) { block.appendChild(notEligibleSection); hasAnyCards = true; }

  if (hasAnyCards && data.checked_universities_count) {
    const note = document.createElement('p');
    note.className = 'checked-count-note';
    note.textContent = `Checked ${data.checked_universities_count} universities from the project data.`;
    block.appendChild(note);
  }

  block.appendChild(renderNextSteps(data.next_steps || [], recommendations));
  const sourcesPanel = renderSources(data.sources || []);
  if (sourcesPanel) block.appendChild(sourcesPanel);
  chatBox.appendChild(block);
  scrollToElement(block);
  return {
    block,
    summaryBody: summaryMessage.querySelector('.message-body'),
  };
}

function addAssistantTurn(data) {
  updateProviderBadge(data);
  const block = document.createElement('section');
  block.className = 'response-block';
  block.appendChild(createMessage('bot', `<div class="answer-content">${formatMarkdown(data.answer || 'I could not generate an answer for this request.')}</div>`));

  const recommendations = data.recommended_universities || [];
  const safeOptions = data.safe_options || [];
  const difficultOptions = data.difficult_options || [];
  const notEligible = data.not_eligible_options || [];

  let hasAnyCards = false;
  const recSection = renderRecommendations(recommendations, 'Best matches');
  if (recSection) { block.appendChild(recSection); hasAnyCards = true; }
  const safeSection = renderRecommendations(safeOptions, 'Safe options');
  if (safeSection) { block.appendChild(safeSection); hasAnyCards = true; }
  const diffSection = renderRecommendations(difficultOptions, 'Difficult but possible');
  if (diffSection) { block.appendChild(diffSection); hasAnyCards = true; }
  const notEligibleSection = renderRecommendations(notEligible, 'Not eligible right now');
  if (notEligibleSection) { block.appendChild(notEligibleSection); hasAnyCards = true; }

  if (hasAnyCards && data.checked_universities_count) {
    const note = document.createElement('p');
    note.className = 'checked-count-note';
    note.textContent = `Checked ${data.checked_universities_count} universities from the project data.`;
    block.appendChild(note);
  }

  block.appendChild(renderNextSteps(data.next_steps || [], recommendations));
  const sourcesPanel = renderSources(data.sources || []);
  if (sourcesPanel) block.appendChild(sourcesPanel);
  chatBox.appendChild(block);
  scrollToElement(block);
}

function addSummaryOnlyMessage(data) {
  updateProviderBadge(data);
  const block = document.createElement('section');
  block.className = 'response-block';
  block.appendChild(createMessage('bot', `<div class="answer-content">${formatMarkdown(data.answer || 'I could not generate an answer for this request.')}</div>`));
  chatBox.appendChild(block);
  scrollToElement(block);
}

function setSelectedUniversity(rec, scroll = true) {
  selectedUniversity = rec;
  selectedUniversityName.textContent = `${rec.short_name || rec.university_name} · ${rec.city || 'Pakistan'}`;
  selectedUniversityBar.classList.remove('hidden');
  if (scroll) scrollToElement(selectedUniversityBar);
}

function clearSelectedUniversity() {
  selectedUniversity = null;
  selectedUniversityBar.classList.add('hidden');
}

function setFastDemoMode(value, persist = true) {
  fastDemoMode = Boolean(value);
  if (fastModeToggle) fastModeToggle.checked = fastDemoMode;
  if (persist) localStorage.setItem(FAST_MODE_KEY, fastDemoMode ? 'true' : 'false');
}

function setBusy(value) {
  isBusy = value;
  sendBtn.disabled = value || !studentProfile;
  userInput.disabled = value || !studentProfile;
  updateChatStatus();
}

async function handleCombinedSend(question) {
  showTyping(loadingStatusLines);
  try {
    const response = await fetch(`${BACKEND_URL}/counsel`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(requestPayload(question)),
    });

    hideTyping();
    if (!response.ok) {
      throw new Error(`Backend returned HTTP ${response.status}`);
    }
    const data = await response.json();
    backendOnline = true;
    setBackendStatus('online', 'Backend connected', 'Live counselling response received.');
    addAssistantTurn(data);
  } catch (error) {
    hideTyping();
    backendOnline = false;
    setBackendStatus(
      'offline',
      'Backend offline',
      'The frontend is working, but the local FastAPI backend is not reachable on port 8000.'
    );
    addSystemMessage('I cannot reach the local counselling backend. Start FastAPI on port 8000, then try again.', 'error');
  } finally {
    setBusy(false);
  }
}

async function requestAISummary(question, recommendData, summaryHandle, selectedId) {
  const slowTimer = window.setTimeout(() => {
    setSummaryMessage(
      summaryHandle.summaryBody,
      'Recommendations are ready. AI summary is taking longer, but you can continue using the cards.',
      'slow'
    );
  }, 12000);

  try {
    const response = await fetch(`${BACKEND_URL}/ai-summary`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        profile: studentProfile,
        question,
        selected_university: selectedId || null,
        recommended_universities: recommendData.recommended_universities || [],
        safe_options: recommendData.safe_options || [],
        difficult_options: recommendData.difficult_options || [],
        not_eligible_options: recommendData.not_eligible_options || [],
        sources: recommendData.sources || [],
      }),
    });

    window.clearTimeout(slowTimer);
    if (!response.ok) {
      throw new Error(`Backend returned HTTP ${response.status}`);
    }
    const data = await response.json();
    backendOnline = true;
    updateProviderBadge(data);
    setBackendStatus('online', 'Backend connected', 'Local AI summary added to the recommendation cards.');
    setSummaryMessage(
      summaryHandle.summaryBody,
      data.answer || 'Recommendations are ready. Use the cards to continue with eligibility, fees, and admission links.',
      'ready'
    );
  } catch (error) {
    window.clearTimeout(slowTimer);
    updateProviderBadge({ provider_used: 'data', selected_model: '' });
    setSummaryMessage(
      summaryHandle.summaryBody,
      'Recommendations are ready. AI summary is taking longer, but you can continue using the cards.',
      'slow'
    );
  }
}

async function requestAISummaryOnly(question, recommendData, selectedId) {
  try {
    const response = await fetch(`${BACKEND_URL}/ai-summary`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        profile: studentProfile,
        question,
        selected_university: selectedId || null,
        recommended_universities: recommendData.recommended_universities || [],
        safe_options: recommendData.safe_options || [],
        difficult_options: recommendData.difficult_options || [],
        not_eligible_options: recommendData.not_eligible_options || [],
        sources: recommendData.sources || [],
      }),
    });
    if (!response.ok) throw new Error(`Backend returned HTTP ${response.status}`);
    return await response.json();
  } catch (error) {
    return null;
  }
}

function renderInfoLinks(links = []) {
  if (!links.length) return null;
  const div = document.createElement('div');
  div.className = 'info-link-row';
  div.innerHTML = links
    .filter((link) => isValidLink(link.url))
    .slice(0, 5)
    .map((link) => `
      <a class="link-action" href="${escapeHtml(link.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(link.label || 'Official link')}</a>
    `).join('');
  return div;
}

function addInfoTurn(data) {
  const block = document.createElement('section');
  block.className = 'response-block';
  const msg = createMessage('bot', `<div class="answer-content">${formatMarkdown(data.answer || '')}</div>`);
  block.appendChild(msg);
  const linkRow = renderInfoLinks(data.links || []);
  if (linkRow) block.appendChild(linkRow);
  if (!data.has_exact_data) {
    const note = document.createElement('p');
    note.className = 'no-exact-data-note';
    note.textContent = 'Note: Official source links are provided; exact stored data was not available for this question.';
    block.appendChild(note);
  }
  chatBox.appendChild(block);
  scrollToElement(block);
}

function addGreetingReply(name) {
  const displayName = name || 'there';
  const msg = createMessage('bot', `Hi ${escapeHtml(displayName)}, I am ready. Ask me which universities are best for you, or ask about eligibility, fees, or admission steps.`);
  chatBox.appendChild(msg);
  scrollToElement(msg);
}

async function handleSend(questionOverride = '') {
  const question = (questionOverride || userInput.value).trim();
  if (!question || isBusy) return;

  if (!studentProfile) {
    showProfileNotice('Save your profile before asking a question.', 'error');
    addSystemMessage('Save your profile first so the answer can be personalised.', 'error');
    return;
  }

  userInput.value = '';
  addUserMessage(question);

  const intent = detectIntent(question);
  if (intent === 'greeting') {
    addGreetingReply(studentProfile.name);
    setBusy(false);
    return;
  }

  setBusy(true);

  if (intent === 'university_info') {
    showTyping(['Looking up university data']);
    try {
      const response = await fetch(`${BACKEND_URL}/university-info`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          profile: studentProfile,
          question,
        }),
      });
      hideTyping();
      if (!response.ok) throw new Error(`Backend returned HTTP ${response.status}`);
      const data = await response.json();
      backendOnline = true;
      addInfoTurn(data);
    } catch (error) {
      hideTyping();
      backendOnline = false;
      setBackendStatus('offline', 'Backend offline', 'The frontend is working, but the local FastAPI backend is not reachable on port 8000.');
      addSystemMessage('I cannot reach the local counselling backend. Start FastAPI on port 8000, then try again.', 'error');
    } finally {
      setBusy(false);
    }
    return;
  }

  if (intent === 'recommendation') {
    showTyping(recommendStatusLines);
    try {
      const response = await fetch(`${BACKEND_URL}/recommend`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestPayload(question)),
      });
      hideTyping();
      if (!response.ok) throw new Error(`Backend returned HTTP ${response.status}`);
      const data = await response.json();
      backendOnline = true;
      lastRecommendationData = data;
      setBackendStatus('online', 'Backend connected', 'Data recommendations are ready. Writing a short AI summary.');
      const summaryHandle = addRecommendationTurn(data);
      setBusy(false);
      requestAISummary(question, data, summaryHandle, data.selected_university || '');
    } catch (error) {
      hideTyping();
      backendOnline = false;
      setBackendStatus('offline', 'Backend offline', 'The frontend is working, but the local FastAPI backend is not reachable on port 8000.');
      addSystemMessage('I cannot reach the local counselling backend. Start FastAPI on port 8000, then try again.', 'error');
      setBusy(false);
    }
    return;
  }

  const selectedId = activeSelectedUniversityId();
  if (lastRecommendationData) {
    showTyping(['Writing a short answer']);
    try {
      const data = await requestAISummaryOnly(question, lastRecommendationData, selectedId);
      hideTyping();
      if (data && data.answer) {
        backendOnline = true;
        addSummaryOnlyMessage(data);
      } else {
        backendOnline = false;
        addSystemMessage('I could not complete the answer. Try asking a different question.', 'error');
      }
    } catch (error) {
      hideTyping();
      backendOnline = false;
      addSystemMessage('I could not complete the answer. Try asking a different question.', 'error');
    } finally {
      setBusy(false);
    }
  } else {
    showTyping(recommendStatusLines);
    try {
      const response = await fetch(`${BACKEND_URL}/recommend`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestPayload(question)),
      });
      hideTyping();
      if (!response.ok) throw new Error(`Backend returned HTTP ${response.status}`);
      const data = await response.json();
      backendOnline = true;
      lastRecommendationData = data;
      const summaryHandle = addRecommendationTurn(data);
      setBusy(false);
      requestAISummary(question, data, summaryHandle, data.selected_university || '');
    } catch (error) {
      hideTyping();
      backendOnline = false;
      addSystemMessage('I cannot reach the local counselling backend. Start FastAPI on port 8000, then try again.', 'error');
      setBusy(false);
    }
  }
}

function sendFollowUp(question, rec) {
  setSelectedUniversity(rec, false);
  handleSend(question);
}

function restoreSavedProfile() {
  const raw = localStorage.getItem(PROFILE_KEY);
  if (!raw) {
    resetProfileForm();
    window.setTimeout(() => {
      if (!studentProfile && !localStorage.getItem(PROFILE_KEY)) resetProfileForm();
    }, 250);
    window.setTimeout(() => {
      if (!studentProfile && !localStorage.getItem(PROFILE_KEY)) resetProfileForm();
    }, 900);
    setEducationFields(eduSystem.value);
    disableChat();
    return;
  }
  try {
    studentProfile = JSON.parse(raw);
    populateProfileForm(studentProfile);
    renderActiveProfile(studentProfile);
    setProfileState('saved', 'Saved');
    saveBtn.textContent = 'Update profile';
    enableChat();
    showProfileNotice('Saved profile restored from this browser.', 'success');
  } catch (error) {
    localStorage.removeItem(PROFILE_KEY);
    disableChat();
  }
}

eduSystem.addEventListener('change', () => {
  setEducationFields(eduSystem.value);
  markProfileDirty();
});

form.addEventListener('input', markProfileDirty);
form.addEventListener('change', markProfileDirty);
saveBtn.addEventListener('click', saveProfile);
clearProfileBtn.addEventListener('click', clearProfile);
clearSelectedBtn.addEventListener('click', clearSelectedUniversity);
if (fastModeToggle) {
  setFastDemoMode(fastDemoMode, false);
  fastModeToggle.addEventListener('change', () => {
    setFastDemoMode(fastModeToggle.checked);
  });
}

chatForm.addEventListener('submit', (event) => {
  event.preventDefault();
  handleSend();
});

document.querySelectorAll('.sample-btn').forEach((button) => {
  button.addEventListener('click', () => {
    userInput.value = button.dataset.q || '';
    userInput.focus();
  });
});

restoreSavedProfile();
refreshBackendStatus();
