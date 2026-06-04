const BACKEND_URL = window.DIGICOUNSELLOR_BACKEND_URL || 'http://localhost:8000';
const PROFILE_KEY = 'digicounsellor.profile.v1';

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

let studentProfile = null;
let selectedUniversity = null;
let typingEl = null;
let backendOnline = false;
let isBusy = false;
let restoringProfile = false;

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
  activeProfileSummary.hidden = false;
  activeProfileSummary.innerHTML = `
    <strong>Using saved profile</strong>
    ${escapeHtml(profile.name)} · ${escapeHtml(profile.preferred_field)} · ${escapeHtml(city)}<br>
    Matric/O Level ${escapeHtml(profile.matric_marks)}% · Inter/A Level ${escapeHtml(profile.inter_marks)}% · ${escapeHtml(typeLabel)}
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
      ? 'Ollama ready'
      : health.lm_studio
        ? 'LM Studio ready'
        : 'Guidance mode available';
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
  const names = {
    ollama: 'Ollama',
    lm_studio: 'LM Studio',
    fallback: 'Guidance mode',
    fallback_after_incomplete: 'Guidance mode',
  };
  const name = names[provider] || provider || 'Provider';
  return model ? `${name} · ${model}` : name;
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
  chatBox.appendChild(createMessage('user', escapeHtml(text)));
  scrollChatToBottom();
}

function addSystemMessage(text, type = '') {
  chatBox.appendChild(createMessage('system', escapeHtml(text), type));
  scrollChatToBottom();
}

function showTyping() {
  hideTyping();
  typingEl = createMessage(
    'bot',
    '<span class="typing-dots" aria-label="DigiCounsellor is typing"><span></span><span></span><span></span></span>'
  );
  chatBox.appendChild(typingEl);
  scrollChatToBottom();
}

function hideTyping() {
  if (typingEl) {
    typingEl.remove();
    typingEl = null;
  }
}

function scrollChatToBottom() {
  chatBox.scrollTop = chatBox.scrollHeight;
}

function fitClass(fit = '') {
  const value = fit.toLowerCase();
  if (value.includes('best')) return 'fit-best';
  if (value.includes('safe')) return 'fit-safe';
  if (value.includes('difficult')) return 'fit-difficult';
  return 'fit-backup';
}

function renderRecommendationCard(rec) {
  const card = document.createElement('article');
  card.className = 'recommendation-card';
  const fields = (rec.fields || []).slice(0, 3).join(', ');
  const firstLinks = (rec.admission_links || []).slice(0, 3);
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
    <div class="link-row">
      ${firstLinks.map((link) => `
        <a class="link-action" href="${escapeHtml(link.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(link.label || 'Official link')}</a>
      `).join('')}
    </div>
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

function renderRecommendations(recommendations = []) {
  if (!recommendations.length) return null;
  const section = document.createElement('section');
  section.className = 'recommendation-set';
  const heading = document.createElement('h3');
  heading.className = 'recommendation-heading';
  heading.textContent = 'Recommended universities';
  const grid = document.createElement('div');
  grid.className = 'recommendation-grid';
  recommendations.slice(0, 5).forEach((rec) => grid.appendChild(renderRecommendationCard(rec)));
  section.append(heading, grid);
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
        return `
          <div class="source-item">
            <strong>${escapeHtml(source.university_name || 'University source')}</strong>
            ${url ? `<a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(url)}</a>` : ''}
            <span>${escapeHtml((source.preview || '').slice(0, 180))}</span>
          </div>
        `;
      }).join('')}
    </div>
  `;
  return details;
}

function addAssistantTurn(data) {
  updateProviderBadge(data);
  const block = document.createElement('section');
  block.className = 'response-block';
  block.appendChild(createMessage('bot', `<div class="answer-content">${formatMarkdown(data.answer || 'I could not generate an answer for this request.')}</div>`));

  const recommendations = data.recommended_universities || [];
  const selectedFromResponse = recommendations.find((rec) => rec.university_id === data.selected_university);
  if (selectedFromResponse && (!selectedUniversity || selectedUniversity.university_id !== selectedFromResponse.university_id)) {
    setSelectedUniversity(selectedFromResponse, false);
  }

  const recSection = renderRecommendations(recommendations);
  if (recSection) block.appendChild(recSection);
  block.appendChild(renderNextSteps(data.next_steps || [], recommendations));
  const sourcesPanel = renderSources(data.sources || []);
  if (sourcesPanel) block.appendChild(sourcesPanel);
  chatBox.appendChild(block);
  scrollChatToBottom();
}

function setSelectedUniversity(rec, scroll = true) {
  selectedUniversity = rec;
  selectedUniversityName.textContent = `${rec.short_name || rec.university_name} · ${rec.city || 'Pakistan'}`;
  selectedUniversityBar.classList.remove('hidden');
  if (scroll) scrollChatToBottom();
}

function clearSelectedUniversity() {
  selectedUniversity = null;
  selectedUniversityBar.classList.add('hidden');
}

function setBusy(value) {
  isBusy = value;
  sendBtn.disabled = value || !studentProfile;
  userInput.disabled = value || !studentProfile;
  updateChatStatus();
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
  setBusy(true);
  showTyping();

  try {
    const response = await fetch(`${BACKEND_URL}/counsel`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        profile: studentProfile,
        question,
        selected_university: selectedUniversity ? selectedUniversity.university_id : '',
      }),
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
