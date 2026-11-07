/**
 * IRONCLAD — AI Personalized Learning Platform
 * Class 10th Mathematics (CBSE / ICSE / State Boards)
 * Multi-Role Controller: Authentication, Educator Command Center, Student Studio
 */

// Application State
const state = {
  token: localStorage.getItem('ironclad_token') || null,
  user: null, // { username, role: 'teacher'|'student', name, student_id, school_name }
  domain: 'class10_maths',
  nodes: [],
  nodeMap: {},
  activeModality: 'worked_examples',
  currentLesson: null,
  activeAssessmentItem: null,
  assessmentStartTime: null,
};

// ============================================================================
// DOM Elements
// ============================================================================
// Views
const authScreen = document.getElementById('authScreen');
const teacherPortal = document.getElementById('teacherPortal');
const studentPortal = document.getElementById('studentPortal');

// Auth Screen
const roleTeacherTab = document.getElementById('roleTeacherTab');
const roleStudentTab = document.getElementById('roleStudentTab');
const loginForm = document.getElementById('loginForm');
const authUsername = document.getElementById('authUsername');
const authPassword = document.getElementById('authPassword');
const loginSubmitBtn = document.getElementById('loginSubmitBtn');
const authErrorMessage = document.getElementById('authErrorMessage');

const quickDemoTeacher = document.getElementById('quickDemoTeacher');
const quickDemoPriya = document.getElementById('quickDemoPriya');
const quickDemoAarav = document.getElementById('quickDemoAarav');
const quickDemoRohit = document.getElementById('quickDemoRohit');

// Teacher Portal
const teacherLogoutBtn = document.getElementById('teacherLogoutBtn');
const refreshTeacherDataBtn = document.getElementById('refreshTeacherDataBtn');
const teacherProfileName = document.getElementById('teacherProfileName');
const kpiTotalStudents = document.getElementById('kpiTotalStudents');
const kpiAvgMastery = document.getElementById('kpiAvgMastery');
const kpiAtRiskCount = document.getElementById('kpiAtRiskCount');
const kpiUnitsCount = document.getElementById('kpiUnitsCount');
const teacherAlertsContainer = document.getElementById('teacherAlertsContainer');
const teacherGraphSvg = document.getElementById('teacherGraphSvg');
const teacherConceptDetail = document.getElementById('teacherConceptDetail');
const teacherStudentsTable = document.getElementById('teacherStudentsTable');

// Student Portal
const studentLogoutBtn = document.getElementById('studentLogoutBtn');
const studentProfileName = document.getElementById('studentProfileName');
const studentStreakCount = document.getElementById('studentStreakCount');
const studentTopicSelect = document.getElementById('studentTopicSelect');
const topicMasteryScore = document.getElementById('topicMasteryScore');
const topicMasteryFill = document.getElementById('topicMasteryFill');
const agencyButtons = document.querySelectorAll('.agency-btn');
const studentSynthesizeBtn = document.getElementById('studentSynthesizeBtn');
const studentLessonTag = document.getElementById('studentLessonTag');
const studentLessonTitle = document.getElementById('studentLessonTitle');
const studentLessonBody = document.getElementById('studentLessonBody');
const studentAssessmentContent = document.getElementById('studentAssessmentContent');
const studentFeedbackBox = document.getElementById('studentFeedbackBox');

// Modal
const explainModal = document.getElementById('explainModal');
const modalCloseBtn = document.getElementById('modalCloseBtn');
const modalStudentTitle = document.getElementById('modalStudentTitle');
const modalBody = document.getElementById('modalBody');

let selectedLoginRole = 'teacher';

// ============================================================================
// Initialization & Auth Flow
// ============================================================================
document.addEventListener('DOMContentLoaded', async () => {
  setupEventListeners();
  await checkExistingSession();
});

function setupEventListeners() {
  // Role selector on auth screen
  roleTeacherTab.addEventListener('click', () => {
    roleTeacherTab.classList.add('active');
    roleStudentTab.classList.remove('active');
    selectedLoginRole = 'teacher';
    authUsername.placeholder = 'teacher@school.edu';
  });

  roleStudentTab.addEventListener('click', () => {
    roleStudentTab.classList.add('active');
    roleTeacherTab.classList.remove('active');
    selectedLoginRole = 'student';
    authUsername.placeholder = 'priya@school.edu';
  });

  // Login form submission
  loginForm.addEventListener('submit', handleManualLogin);
  loginSubmitBtn.addEventListener('click', handleManualLogin);

  // Quick Demo Access Buttons
  quickDemoTeacher.addEventListener('click', () => handleDemoLogin('teacher'));
  quickDemoPriya.addEventListener('click', () => handleDemoLogin('student', 's_priya'));
  quickDemoAarav.addEventListener('click', () => handleDemoLogin('student', 's_aarav'));
  quickDemoRohit.addEventListener('click', () => handleDemoLogin('student', 's_rohit'));

  // Logout Buttons
  teacherLogoutBtn.addEventListener('click', handleLogout);
  studentLogoutBtn.addEventListener('click', handleLogout);

  // Teacher Analytics Refresh
  refreshTeacherDataBtn.addEventListener('click', loadTeacherAnalytics);

  // Student Agency Modality Selection
  agencyButtons.forEach((btn) => {
    btn.addEventListener('click', () => {
      agencyButtons.forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');
      state.activeModality = btn.dataset.modality;
      updateStudentModalityPreference(state.activeModality);
    });
  });

  // Student Topic Change
  studentTopicSelect.addEventListener('change', () => {
    updateStudentTopicMasteryDisplay();
  });

  // Synthesize Lesson Button
  studentSynthesizeBtn.addEventListener('click', generateStudentLesson);

  // Modal Close
  modalCloseBtn.addEventListener('click', () => explainModal.classList.add('hidden'));
  explainModal.addEventListener('click', (e) => {
    if (e.target === explainModal) explainModal.classList.add('hidden');
  });
}

async function checkExistingSession() {
  if (!state.token) {
    showView('auth');
    return;
  }

  try {
    const res = await fetch('/api/auth/me', {
      headers: { Authorization: `Bearer ${state.token}` },
    });
    if (!res.ok) throw new Error('Session invalid');
    const data = await res.json();
    state.user = data.user;
    routeAuthenticatedUser();
  } catch (err) {
    state.token = null;
    localStorage.removeItem('ironclad_token');
    showView('auth');
  }
}

async function handleManualLogin() {
  authErrorMessage.classList.add('hidden');
  const username = authUsername.value.trim();
  const password = authPassword.value.trim();

  if (!username) {
    showAuthError('Please enter your institutional email or username.');
    return;
  }

  loginSubmitBtn.disabled = true;
  loginSubmitBtn.textContent = 'Authenticating...';

  try {
    const res = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        username,
        password: password || 'demo',
        role: selectedLoginRole,
      }),
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.error || 'Authentication failed');
    }

    state.token = data.token;
    state.user = data.user;
    localStorage.setItem('ironclad_token', data.token);

    routeAuthenticatedUser();
  } catch (err) {
    showAuthError(err.message);
  } finally {
    loginSubmitBtn.disabled = false;
    loginSubmitBtn.textContent = 'Authenticate to Portal';
  }
}

async function handleDemoLogin(role, studentId = null) {
  authErrorMessage.classList.add('hidden');
  try {
    const res = await fetch('/api/auth/demo', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ role, student_id: studentId }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Demo login failed');

    state.token = data.token;
    state.user = data.user;
    localStorage.setItem('ironclad_token', data.token);

    routeAuthenticatedUser();
  } catch (err) {
    showAuthError(err.message);
  }
}

async function handleLogout() {
  if (state.token) {
    try {
      await fetch('/api/auth/logout', {
        method: 'POST',
        headers: { Authorization: `Bearer ${state.token}` },
      });
    } catch (e) {}
  }
  state.token = null;
  state.user = null;
  localStorage.removeItem('ironclad_token');
  showView('auth');
}

function showAuthError(msg) {
  authErrorMessage.textContent = msg;
  authErrorMessage.classList.remove('hidden');
}

function showView(viewName) {
  authScreen.classList.remove('active');
  teacherPortal.classList.remove('active');
  studentPortal.classList.remove('active');

  if (viewName === 'auth') authScreen.classList.add('active');
  if (viewName === 'teacher') teacherPortal.classList.add('active');
  if (viewName === 'student') studentPortal.classList.add('active');
}

function routeAuthenticatedUser() {
  if (!state.user) {
    showView('auth');
    return;
  }

  if (state.user.role === 'teacher') {
    showView('teacher');
    teacherProfileName.textContent = state.user.name || 'Dr. Sunita Sharma';
    loadCurriculumData().then(() => {
      loadTeacherAnalytics();
    });
  } else {
    showView('student');
    studentProfileName.textContent = state.user.name || 'Priya Sharma';
    loadCurriculumData().then(() => {
      initializeStudentStudio();
    });
  }
}

// ============================================================================
// Curriculum Graph Data Loader
// ============================================================================
async function loadCurriculumData() {
  try {
    const res = await fetch(`/api/curriculum?domain=${state.domain}`);
    const data = await res.json();
    state.nodes = data.nodes || [];
    state.nodeMap = {};
    state.nodes.forEach((n) => {
      state.nodeMap[n.id] = n;
    });
  } catch (err) {
    console.error('Failed to load curriculum:', err);
  }
}

// ============================================================================
// 1. TEACHER PORTAL CONTROLLER
// ============================================================================
async function loadTeacherAnalytics() {
  try {
    const summaryRes = await fetch(`/api/class-summary?domain=${state.domain}`);
    const summary = await summaryRes.json();

    kpiTotalStudents.textContent = summary.total_students || 4;
    kpiAvgMastery.textContent = `${summary.average_mastery_pct || 74.8}%`;
    kpiAtRiskCount.textContent = summary.students_requiring_intervention || 2;
    kpiUnitsCount.textContent = `${state.nodes.length} Units`;

    // Render Diagnostic Alerts
    renderTeacherAlerts(summary.active_alerts || []);

    // Render DAG Graph
    renderTeacherDAG();

    // Render Student Cohort Table
    const studentsRes = await fetch(`/api/students?domain=${state.domain}`);
    const students = await studentsRes.json();
    renderTeacherStudentsTable(students);
  } catch (err) {
    console.error('Failed to load teacher analytics:', err);
  }
}

function renderTeacherAlerts(alerts) {
  if (!alerts || alerts.length === 0) {
    teacherAlertsContainer.innerHTML = `
      <div style="padding: 1.5rem; color: var(--text-muted); text-align: center; background: var(--bg-input); border-radius: var(--radius-md);">
        All enrolled Class 10 candidates are currently meeting mastery benchmarks.
      </div>
    `;
    return;
  }

  teacherAlertsContainer.innerHTML = alerts
    .map((alert) => {
      const isHigh = alert.severity === 'high';
      const cardClass = isHigh ? 'alert-card high' : 'alert-card medium';
      const severityTag = isHigh ? 'tag-pill rose' : 'tag-pill amber';

      return `
        <div class="${cardClass}">
          <div class="alert-card-header">
            <span class="alert-student-title">${alert.student_name}</span>
            <span class="${severityTag}">${alert.severity.toUpperCase()} PRIORITY</span>
          </div>
          <div class="alert-message">${alert.message}</div>
          <div class="alert-actions-row">
            <button class="alert-explain-btn" onclick="openDiagnosticModal('${alert.student_id}', '${alert.concept_id}')">
              <svg class="svg-icon sm" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
              </svg>
              Inspect Diagnostic Evidence
            </button>
            <button class="alert-resolve-btn" onclick="resolveAlert('${alert.alert_id}')">
              Mark Resolved
            </button>
          </div>
        </div>
      `;
    })
    .join('');
}

window.resolveAlert = async function (alertId) {
  try {
    await fetch('/api/resolve-alert', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ alert_id: alertId }),
    });
    loadTeacherAnalytics();
  } catch (err) {
    console.error('Failed to resolve alert:', err);
  }
};

window.openDiagnosticModal = async function (studentId, conceptId) {
  try {
    const res = await fetch(`/api/explain/${studentId}?domain=${state.domain}&concept=${conceptId || ''}`);
    const expl = await res.json();

    modalStudentTitle.textContent = `Diagnostic Intervention Rationale: ${expl.student_name}`;
    modalBody.innerHTML = `
      <div>
        <strong style="color: #ffffff;">Target Board Concept:</strong> ${expl.target_concept}<br>
        <strong style="color: #ffffff;">Struggle Classification:</strong> <span class="tag-pill rose">${expl.struggle_type}</span>
      </div>

      <div style="background: rgba(99, 102, 241, 0.1); border: 1px solid rgba(99, 102, 241, 0.3); padding: 1rem; border-radius: 8px;">
        <strong style="color: #67e8f9;">Recommended Educator Action:</strong>
        <p style="margin-top: 0.35rem; color: #ffffff;">${expl.recommended_action}</p>
        ${
          expl.prerequisite_root_cause
            ? `<div style="margin-top: 0.5rem; font-size: 0.8rem; color: #fca5a5;">
                Prerequisite Deficit Identified: <strong>${expl.prerequisite_root_cause}</strong>
               </div>`
            : ''
        }
      </div>

      <div>
        <strong style="color: #ffffff;">Automated Diagnostic Chain &amp; Evidence Points:</strong>
        <ul class="evidence-list">
          ${expl.evidence_points.map((pt) => `<li>${pt}</li>`).join('')}
        </ul>
      </div>

      <div style="background: rgba(16, 185, 129, 0.08); border: 1px solid rgba(16, 185, 129, 0.3); padding: 1rem; border-radius: 8px;">
        <strong style="color: #6ee7b7;">Suggested Teaching Strategy (Pedagogical Scaffolding):</strong>
        <p style="margin-top: 0.35rem; color: #e2e8f0;">${expl.suggested_teaching_strategy}</p>
      </div>
    `;

    explainModal.classList.remove('hidden');
  } catch (err) {
    console.error('Failed to fetch explanation:', err);
  }
};

function renderTeacherDAG() {
  teacherGraphSvg.innerHTML = '';
  if (!state.nodes || state.nodes.length === 0) return;

  const width = teacherGraphSvg.clientWidth || 800;
  const height = 480;

  // Group nodes by difficulty
  const layers = {};
  state.nodes.forEach((n) => {
    const diff = n.difficulty || 1;
    if (!layers[diff]) layers[diff] = [];
    layers[diff].push(n);
  });

  const diffKeys = Object.keys(layers).sort((a, b) => Number(a) - Number(b));
  const numLayers = diffKeys.length;
  const colWidth = (width - 140) / Math.max(1, numLayers - 1 || 1);

  const nodePositions = {};
  diffKeys.forEach((diff, colIdx) => {
    const layerNodes = layers[diff];
    const rowHeight = height / (layerNodes.length + 1);
    layerNodes.forEach((node, rowIdx) => {
      const x = 70 + colIdx * colWidth;
      const y = (rowIdx + 1) * rowHeight;
      nodePositions[node.id] = { x, y, node };
    });
  });

  // SVG Arrow marker
  const defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
  defs.innerHTML = `
    <marker id="teacherArrow" markerWidth="8" markerHeight="6" refX="24" refY="3" orient="auto">
      <polygon points="0 0, 8 3, 0 6" fill="#6366f1" opacity="0.8" />
    </marker>
  `;
  teacherGraphSvg.appendChild(defs);

  // Edges
  state.nodes.forEach((node) => {
    const targetPos = nodePositions[node.id];
    if (!targetPos) return;

    node.prerequisites.forEach((prereqId) => {
      const sourcePos = nodePositions[prereqId];
      if (!sourcePos) return;

      const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
      const dx = targetPos.x - sourcePos.x;
      const dy = targetPos.y - sourcePos.y;
      const cx1 = sourcePos.x + dx * 0.5;
      const cy1 = sourcePos.y;
      const cx2 = sourcePos.x + dx * 0.5;
      const cy2 = targetPos.y;

      path.setAttribute(
        'd',
        `M ${sourcePos.x} ${sourcePos.y} C ${cx1} ${cy1}, ${cx2} ${cy2}, ${targetPos.x} ${targetPos.y}`
      );
      path.setAttribute('fill', 'none');
      path.setAttribute('stroke', 'rgba(99, 102, 241, 0.4)');
      path.setAttribute('stroke-width', '2');
      path.setAttribute('marker-end', 'url(#teacherArrow)');
      teacherGraphSvg.appendChild(path);
    });
  });

  // Nodes
  Object.values(nodePositions).forEach(({ x, y, node }) => {
    const group = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    group.style.cursor = 'pointer';

    const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    circle.setAttribute('cx', x);
    circle.setAttribute('cy', y);
    circle.setAttribute('r', '18');
    circle.setAttribute('fill', '#101626');
    circle.setAttribute('stroke', '#6366f1');
    circle.setAttribute('stroke-width', '2.5');
    group.appendChild(circle);

    const label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    label.setAttribute('x', x);
    label.setAttribute('y', y + 32);
    label.setAttribute('text-anchor', 'middle');
    label.setAttribute('fill', '#cbd5e1');
    label.setAttribute('font-size', '10px');
    label.setAttribute('font-weight', '600');
    label.setAttribute('font-family', 'Plus Jakarta Sans');

    const cleanName = node.name.replace(/Class 10th |NCERT /g, '');
    const shortName = cleanName.length > 18 ? cleanName.substring(0, 16) + '...' : cleanName;
    label.textContent = shortName;
    group.appendChild(label);

    group.addEventListener('click', () => {
      showTeacherNodeDetail(node);
    });

    teacherGraphSvg.appendChild(group);
  });
}

function showTeacherNodeDetail(concept) {
  teacherConceptDetail.innerHTML = `
    <div style="border-bottom: 1px solid var(--border-subtle); padding-bottom: 0.85rem; margin-bottom: 1rem;">
      <span class="tag-pill indigo">NCERT Difficulty Level ${concept.difficulty}/5</span>
      <h4 style="color: #ffffff; font-size: 1.1rem; margin-top: 0.35rem;">${concept.name}</h4>
    </div>
    
    <p style="font-size: 0.85rem; color: #94a3b8; line-height: 1.5; margin-bottom: 1rem;">${concept.description}</p>
    
    <div style="margin-bottom: 1rem;">
      <strong style="font-size: 0.78rem; text-transform: uppercase; color: #a5b4fc; letter-spacing: 0.05em;">Upstream Prerequisites:</strong>
      ${
        concept.prerequisites && concept.prerequisites.length > 0
          ? `<ul class="evidence-list">${concept.prerequisites.map((p) => `<li><code>${p}</code></li>`).join('')}</ul>`
          : '<p style="font-size: 0.8rem; color: var(--text-muted); margin-top: 0.25rem;">None (Foundational Class 10 Unit)</p>'
      }
    </div>

    <div style="margin-bottom: 1rem;">
      <strong style="font-size: 0.78rem; text-transform: uppercase; color: #a5b4fc; letter-spacing: 0.05em;">Curricular Learning Objectives:</strong>
      <ul class="evidence-list">
        ${concept.learning_objectives.map((obj) => `<li>${obj}</li>`).join('')}
      </ul>
    </div>

    ${
      concept.real_world_context
        ? `
      <div style="background: rgba(255,255,255,0.03); padding: 0.85rem; border-radius: 6px;">
        <strong style="font-size: 0.75rem; color: #67e8f9; text-transform: uppercase;">Real-World Practical Context:</strong>
        <p style="font-size: 0.8rem; color: #cbd5e1; margin-top: 0.25rem;">${concept.real_world_context}</p>
      </div>`
        : ''
    }
  `;
}

function renderTeacherStudentsTable(students) {
  teacherStudentsTable.innerHTML = students
    .map((s) => {
      let statusHtml = '<span class="tag-pill emerald">Mastered</span>';
      if (s.active_struggle) {
        statusHtml = `<span class="tag-pill rose">Struggle: ${s.active_struggle.replace('c10_', '')}</span>`;
      } else if (s.learning_pace === 'needs_scaffolding') {
        statusHtml = '<span class="tag-pill amber">Needs Scaffolding</span>';
      }

      return `
        <tr>
          <td>
            <strong style="color: #ffffff;">${s.name}</strong><br>
            <small style="color: var(--text-muted);">${s.student_id} &bull; Section 10-A</small>
          </td>
          <td><span style="font-family: var(--font-mono); font-size: 0.8rem;">${s.learning_pace}</span></td>
          <td><span class="tag-pill indigo">${s.preferred_modality}</span></td>
          <td><strong style="color: #ffffff;">${s.correct_assessments}</strong> / ${s.total_assessments} items</td>
          <td>${statusHtml}</td>
          <td>
            <button class="action-btn secondary" style="font-size: 0.78rem; padding: 0.4rem 0.75rem;" onclick="openDiagnosticModal('${s.student_id}', '${s.active_struggle || ''}')">
              Explain Rationale
            </button>
          </td>
        </tr>
      `;
    })
    .join('');
}

// ============================================================================
// 2. STUDENT PORTAL CONTROLLER
// ============================================================================
async function initializeStudentStudio() {
  studentProfileName.textContent = state.user.name || 'Priya Sharma';

  // Populate syllabus dropdown
  studentTopicSelect.innerHTML = state.nodes
    .map(
      (n) => `
      <option value="${n.id}">${n.name}</option>
    `
    )
    .join('');

  // Default to quadratic equations or active struggle
  if (state.user.student_id === 's_priya') {
    studentTopicSelect.value = 'c10_quadratic_equations';
  } else if (state.user.student_id === 's_rohit') {
    studentTopicSelect.value = 'c10_triangles';
  } else if (state.nodes.length > 0) {
    studentTopicSelect.value = state.nodes[0].id;
  }

  await updateStudentTopicMasteryDisplay();
  await generateStudentLesson();
}

async function updateStudentTopicMasteryDisplay() {
  const conceptId = studentTopicSelect.value;
  const studentId = state.user.student_id || 's_priya';

  try {
    const res = await fetch(`/api/student/${studentId}`);
    if (res.ok) {
      const student = await res.json();
      const mastery = student.concept_mastery ? student.concept_mastery[conceptId] : null;
      const pct = mastery !== undefined && mastery !== null ? Math.round(mastery * 100) : 50;

      topicMasteryScore.textContent = `${pct}%`;
      topicMasteryFill.style.width = `${pct}%`;

      if (pct >= 80) {
        topicMasteryFill.style.background = '#10b981';
      } else if (pct >= 50) {
        topicMasteryFill.style.background = '#f59e0b';
      } else {
        topicMasteryFill.style.background = '#f43f5e';
      }

      if (student.streak_correct > 0) {
        studentStreakCount.textContent = `${student.streak_correct} In a Row`;
      } else {
        studentStreakCount.textContent = 'Active Learning';
      }
    }
  } catch (err) {
    console.error('Failed to load student mastery:', err);
  }
}

async function updateStudentModalityPreference(modality) {
  const studentId = state.user.student_id || 's_priya';
  try {
    await fetch('/api/student/preference', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ student_id: studentId, modality }),
    });
  } catch (err) {
    console.error('Failed to save modality agency preference:', err);
  }
}

async function generateStudentLesson() {
  const studentId = state.user.student_id || 's_priya';
  const conceptId = studentTopicSelect.value;
  if (!conceptId) return;

  studentSynthesizeBtn.disabled = true;
  studentSynthesizeBtn.textContent = 'Synthesizing with Gemma 4...';

  try {
    const res = await fetch('/api/lesson', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        student_id: studentId,
        concept_id: conceptId,
        domain: state.domain,
        modality: state.activeModality,
      }),
    });

    const lesson = await res.json();
    state.currentLesson = lesson;

    studentLessonTitle.textContent = lesson.concept_name;
    studentLessonTag.textContent = `NCERT SEQUENCE &bull; ${lesson.modality.toUpperCase()}`;

    // Render formatted lesson
    studentLessonBody.innerHTML = `
      ${
        lesson.socratic_scaffolding
          ? `<div style="background: rgba(99, 102, 241, 0.12); border-left: 4px solid var(--indigo); padding: 0.85rem 1.15rem; border-radius: 6px; margin-bottom: 1.25rem; font-size: 0.9rem; color: #c7d2fe;">
              <strong>Pedagogical Scaffolding:</strong> ${lesson.socratic_scaffolding}
             </div>`
          : ''
      }
      <div style="font-size: 0.95rem; line-height: 1.7; color: #f1f5f9;">
        ${lesson.explanation.replace(/\n\n/g, '<br><br>')}
      </div>

      <div class="lesson-section-box">
        <div class="lesson-section-title">Worked Example &amp; Board Derivation</div>
        <div style="white-space: pre-wrap; font-size: 0.9rem; color: #e2e8f0;">${lesson.worked_example}</div>
      </div>

      <div class="lesson-section-box" style="border-left: 3px solid var(--cyan);">
        <div class="lesson-section-title" style="color: #67e8f9;">Guided Socratic Practice</div>
        <div style="font-size: 0.9rem; color: #e2e8f0;">${lesson.guided_exercise}</div>
      </div>
    `;

    // Render assessment item
    renderAssessmentItem(lesson.assessment_items);
  } catch (err) {
    console.error('Failed to generate lesson:', err);
    studentLessonBody.innerHTML = `<p style="color: var(--rose);">Error synthesizing lesson: ${err.message}</p>`;
  } finally {
    studentSynthesizeBtn.disabled = false;
    studentSynthesizeBtn.textContent = 'Synthesize Tailored Lesson';
  }
}

function renderAssessmentItem(items) {
  studentFeedbackBox.classList.add('hidden');
  if (!items || items.length === 0) {
    studentAssessmentContent.innerHTML = '<p class="text-dim">No assessment questions available for this unit.</p>';
    return;
  }

  const q = items[0];
  state.activeAssessmentItem = q;
  state.assessmentStartTime = Date.now();

  const optionsHtml = q.options && q.options.length > 0
    ? q.options
        .map(
          (opt) => `
        <label class="assessment-option-label">
          <input type="radio" name="boardAssessmentOption" value="${opt}">
          <span>${opt}</span>
        </label>
      `
        )
        .join('')
    : `
      <input type="text" id="freeformAnswerInput" class="auth-input" placeholder="Type your final answer...">
    `;

  studentAssessmentContent.innerHTML = `
    <div class="assessment-question-text">${q.question}</div>
    <div class="assessment-options-list">
      ${optionsHtml}
    </div>
    <button id="submitAssessmentBtn" class="action-btn primary full-width" style="margin-top: 1rem;">
      Submit Answer for Socratic Evaluation
    </button>
  `;

  document.getElementById('submitAssessmentBtn').addEventListener('click', submitStudentAssessment);
}

async function submitStudentAssessment() {
  if (!state.activeAssessmentItem) return;

  let answer = '';
  const radio = document.querySelector('input[name="boardAssessmentOption"]:checked');
  if (radio) {
    answer = radio.value;
  } else {
    const input = document.getElementById('freeformAnswerInput');
    if (input) answer = input.value.trim();
  }

  if (!answer) {
    alert('Please select or provide an answer before submitting.');
    return;
  }

  const latencySec = (Date.now() - (state.assessmentStartTime || Date.now())) / 1000;
  const studentId = state.user.student_id || 's_priya';
  const conceptId = studentTopicSelect.value;

  const submitBtn = document.getElementById('submitAssessmentBtn');
  submitBtn.disabled = true;
  submitBtn.textContent = 'Evaluating Socratic Feedback...';

  try {
    const res = await fetch('/api/assess', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        student_id: studentId,
        concept_id: conceptId,
        item_id: state.activeAssessmentItem.id,
        student_answer: answer,
        domain: state.domain,
        latency_sec: latencySec,
      }),
    });

    const result = await res.json();

    studentFeedbackBox.className = `feedback-box ${result.is_correct ? 'correct' : 'socratic'}`;
    studentFeedbackBox.innerHTML = `
      <div class="feedback-title">
        <svg class="svg-icon sm" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          ${
            result.is_correct
              ? '<polyline points="20 6 9 17 4 12"/>'
              : '<circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>'
          }
        </svg>
        ${result.is_correct ? 'Correct! Mastery Score Advanced' : 'Socratic Pedagogical Guidance'}
      </div>
      <div class="feedback-message">${result.socratic_feedback}</div>
      ${
        result.prerequisite_gap_detected
          ? `
        <div class="prereq-alert-banner">
          <strong>Upstream Prerequisite Deficit Detected:</strong> <code>${result.prerequisite_gap_detected}</code><br>
          Our knowledge graph identified that reviewing this prerequisite will directly unlock mastery of this topic.
        </div>
      `
          : ''
      }
    `;

    studentFeedbackBox.classList.remove('hidden');

    // Update mastery meter
    await updateStudentTopicMasteryDisplay();
  } catch (err) {
    console.error('Failed to submit assessment:', err);
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = 'Submit Answer for Socratic Evaluation';
  }
}
