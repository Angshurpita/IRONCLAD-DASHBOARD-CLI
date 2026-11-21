/**
 * IRONCLAD — AI Personalized Learning & Educator Intelligence
 * Class 10th Mathematics (CBSE / ICSE / State Boards)
 * 
 * Features:
 * 1. 3D Background Canvas Engine: 3D rotating polyhedra, orbital rings, and knowledge lattice
 * 2. Real Authentication Layer: Register, Login, Session Persistence, Role Routing
 * 3. Dynamic Student Studio: Curriculum, Agency Modalities, Lesson Synthesis, Socratic Assessment
 * 4. Educator Intelligence Center: Dynamic KPIs, Diagnostic Alerts, Prerequisite DAG, Real Roster
 */

// ============================================================================
// 1. GLOBAL STATE
// ============================================================================
const state = {
  token: localStorage.getItem('ironclad_token') || null,
  user: null, // { username, role, name, student_id, school_name }
  domain: 'class10_maths',
  nodes: [],
  nodeMap: {},
  authMode: 'login', // 'login' | 'register'
  authRole: 'student', // 'student' | 'teacher'
  activeModality: 'worked_examples',
  currentLesson: null,
  activeAssessmentItem: null,
  assessmentStartTime: null,
};

// ============================================================================
// 2. DOM ELEMENT REFERENCES
// ============================================================================
// Views
const authScreen = document.getElementById('authScreen');
const studentPortal = document.getElementById('studentPortal');
const teacherPortal = document.getElementById('teacherPortal');
const appNav = document.getElementById('appNav');

// Top Nav
const navRoleTag = document.getElementById('navRoleTag');
const navUserName = document.getElementById('navUserName');
const navUserRole = document.getElementById('navUserRole');
const navUserAvatar = document.getElementById('navUserAvatar');
const navStudentStreak = document.getElementById('navStudentStreak');
const streakCountText = document.getElementById('streakCountText');
const navRefreshBtn = document.getElementById('navRefreshBtn');
const globalSignOutBtn = document.getElementById('globalSignOutBtn');

// Auth Screen Elements
const modeSignInTab = document.getElementById('modeSignInTab');
const modeRegisterTab = document.getElementById('modeRegisterTab');
const roleStudentToggle = document.getElementById('roleStudentToggle');
const roleTeacherToggle = document.getElementById('roleTeacherToggle');
const authForm = document.getElementById('authForm');
const authNameFieldGroup = document.getElementById('authNameFieldGroup');
const authFullName = document.getElementById('authFullName');
const authUsernameLabel = document.getElementById('authUsernameLabel');
const authUsername = document.getElementById('authUsername');
const authPassword = document.getElementById('authPassword');
const authSchoolFieldGroup = document.getElementById('authSchoolFieldGroup');
const authSchoolName = document.getElementById('authSchoolName');
const authAlertBanner = document.getElementById('authAlertBanner');
const authSubmitBtn = document.getElementById('authSubmitBtn');

// Student Studio Elements
const studentTopicSelect = document.getElementById('studentTopicSelect');
const topicMasteryScore = document.getElementById('topicMasteryScore');
const topicMasteryFill = document.getElementById('topicMasteryFill');
const modalityCards = document.querySelectorAll('.modality-card');
const studentSynthesizeBtn = document.getElementById('studentSynthesizeBtn');
const studentLessonTag = document.getElementById('studentLessonTag');
const studentLessonTitle = document.getElementById('studentLessonTitle');
const studentLessonBody = document.getElementById('studentLessonBody');
const studentAssessmentContent = document.getElementById('studentAssessmentContent');
const studentFeedbackBox = document.getElementById('studentFeedbackBox');

// Educator Elements
const kpiTotalStudents = document.getElementById('kpiTotalStudents');
const kpiAvgMastery = document.getElementById('kpiAvgMastery');
const kpiAtRiskCount = document.getElementById('kpiAtRiskCount');
const kpiUnitsCount = document.getElementById('kpiUnitsCount');
const teacherAlertsContainer = document.getElementById('teacherAlertsContainer');
const teacherGraphSvg = document.getElementById('teacherGraphSvg');
const teacherConceptDetail = document.getElementById('teacherConceptDetail');
const teacherStudentsTable = document.getElementById('teacherStudentsTable');

// Diagnostic Modal
const explainModal = document.getElementById('explainModal');
const modalCloseBtn = document.getElementById('modalCloseBtn');
const modalStudentTitle = document.getElementById('modalStudentTitle');
const modalBody = document.getElementById('modalBody');

// ============================================================================
// 3. 3D BACKGROUND CANVAS ANIMATION ENGINE ("Of Different Stuff")
// ============================================================================
function init3DBackground() {
  const canvas = document.getElementById('bg3dCanvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  if (!ctx) return;

  let width = (canvas.width = window.innerWidth);
  let height = (canvas.height = window.innerHeight);
  let dpr = window.devicePixelRatio || 1;

  function resize() {
    dpr = window.devicePixelRatio || 1;
    width = window.innerWidth;
    height = window.innerHeight;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    canvas.style.width = width + 'px';
    canvas.style.height = height + 'px';
    ctx.scale(dpr, dpr);
  }
  resize();
  window.addEventListener('resize', resize);

  // Mouse interaction state
  let mouse = { x: width / 2, y: height / 2, targetX: width / 2, targetY: height / 2 };
  window.addEventListener('mousemove', (e) => {
    mouse.targetX = e.clientX;
    mouse.targetY = e.clientY;
  });

  // 3D Math Utilities
  function rotateX(v, angle) {
    const cos = Math.cos(angle);
    const sin = Math.sin(angle);
    return { x: v.x, y: v.y * cos - v.z * sin, z: v.y * sin + v.z * cos };
  }
  function rotateY(v, angle) {
    const cos = Math.cos(angle);
    const sin = Math.sin(angle);
    return { x: v.x * cos + v.z * sin, y: v.y, z: -v.x * sin + v.z * cos };
  }
  function rotateZ(v, angle) {
    const cos = Math.cos(angle);
    const sin = Math.sin(angle);
    return { x: v.x * cos - v.y * sin, y: v.x * sin + v.y * cos, z: v.z };
  }
  function project(v, cx, cy, fov = 400, dist = 500) {
    const factor = fov / (dist + v.z);
    return {
      x: cx + v.x * factor,
      y: cy + v.y * factor,
      scale: factor,
      z: v.z,
    };
  }

  // 1. Icosahedron Geometry
  const phi = (1 + Math.sqrt(5)) / 2;
  const icoRawVertices = [
    [-1, phi, 0], [1, phi, 0], [-1, -phi, 0], [1, -phi, 0],
    [0, -1, phi], [0, 1, phi], [0, -1, -phi], [0, 1, -phi],
    [phi, 0, -1], [phi, 0, 1], [-phi, 0, -1], [-phi, 0, 1]
  ];
  const icoVertices = icoRawVertices.map(([x, y, z]) => {
    const len = Math.sqrt(x*x + y*y + z*z);
    return { x: (x / len) * 110, y: (y / len) * 110, z: (z / len) * 110 };
  });
  const icoEdges = [];
  for (let i = 0; i < icoVertices.length; i++) {
    for (let j = i + 1; j < icoVertices.length; j++) {
      const dx = icoVertices[i].x - icoVertices[j].x;
      const dy = icoVertices[i].y - icoVertices[j].y;
      const dz = icoVertices[i].z - icoVertices[j].z;
      const d = Math.sqrt(dx*dx + dy*dy + dz*dz);
      if (Math.abs(d - 115) < 25) {
        icoEdges.push([i, j]);
      }
    }
  }

  // 2. Nested Cube Geometry
  const cubeRaw = [
    [-1, -1, -1], [1, -1, -1], [1, 1, -1], [-1, 1, -1],
    [-1, -1, 1], [1, -1, 1], [1, 1, 1], [-1, 1, 1]
  ];
  const cubeVertices = cubeRaw.map(([x, y, z]) => ({ x: x * 65, y: y * 65, z: z * 65 }));
  const cubeEdges = [
    [0, 1], [1, 2], [2, 3], [3, 0],
    [4, 5], [5, 6], [6, 7], [7, 4],
    [0, 4], [1, 5], [2, 6], [3, 7]
  ];

  // 3. Orbital Torus Ring
  const ringPoints = [];
  const ringCount = 28;
  for (let i = 0; i < ringCount; i++) {
    const th = (i / ringCount) * Math.PI * 2;
    ringPoints.push({ x: Math.cos(th) * 150, y: Math.sin(th) * 150, z: 0 });
  }

  // 4. Floating 3D Knowledge Lattice Nodes
  const latticeCount = 38;
  const latticeNodes = [];
  for (let i = 0; i < latticeCount; i++) {
    latticeNodes.push({
      x: (Math.random() - 0.5) * 800,
      y: (Math.random() - 0.5) * 600,
      z: (Math.random() - 0.5) * 500,
      vx: (Math.random() - 0.5) * 0.4,
      vy: (Math.random() - 0.5) * 0.4,
      vz: (Math.random() - 0.5) * 0.4,
      radius: 2 + Math.random() * 2.5,
    });
  }

  let angleA = 0;
  let angleB = 0;

  function renderLoop() {
    ctx.clearRect(0, 0, width, height);

    // Smooth mouse parallax
    mouse.x += (mouse.targetX - mouse.x) * 0.05;
    mouse.y += (mouse.targetY - mouse.y) * 0.05;
    const tiltX = (mouse.y - height / 2) * 0.0004;
    const tiltY = (mouse.x - width / 2) * 0.0004;

    angleA += 0.006;
    angleB += 0.004;

    // Center coordinates for multiple 3D elements
    const centerIco = { x: width * 0.85, y: height * 0.32 };
    const centerCube = { x: width * 0.15, y: height * 0.72 };

    // --- A. Render 3D Icosahedron ---
    const rotIcoVerts = icoVertices.map((v) => {
      let p = rotateX(v, angleA + tiltX);
      p = rotateY(p, angleB + tiltY);
      p = rotateZ(p, angleA * 0.5);
      return project(p, centerIco.x, centerIco.y, 450, 480);
    });

    ctx.strokeStyle = 'rgba(79, 70, 229, 0.18)';
    ctx.lineWidth = 1.2;
    icoEdges.forEach(([i, j]) => {
      const p1 = rotIcoVerts[i];
      const p2 = rotIcoVerts[j];
      ctx.beginPath();
      ctx.moveTo(p1.x, p1.y);
      ctx.lineTo(p2.x, p2.y);
      ctx.stroke();
    });

    rotIcoVerts.forEach((p) => {
      ctx.fillStyle = 'rgba(99, 102, 241, 0.3)';
      ctx.beginPath();
      ctx.arc(p.x, p.y, Math.max(1, 2.5 * p.scale), 0, Math.PI * 2);
      ctx.fill();
    });

    // --- B. Render 3D Rotating Cube ---
    const rotCubeVerts = cubeVertices.map((v) => {
      let p = rotateX(v, -angleB + tiltX);
      p = rotateY(p, angleA * 0.8 + tiltY);
      return project(p, centerCube.x, centerCube.y, 400, 480);
    });

    ctx.strokeStyle = 'rgba(2, 132, 199, 0.16)';
    ctx.lineWidth = 1.2;
    cubeEdges.forEach(([i, j]) => {
      const p1 = rotCubeVerts[i];
      const p2 = rotCubeVerts[j];
      ctx.beginPath();
      ctx.moveTo(p1.x, p1.y);
      ctx.lineTo(p2.x, p2.y);
      ctx.stroke();
    });

    // --- C. Render 3D Orbital Ring Around Icosahedron ---
    const rotRingVerts = ringPoints.map((v) => {
      let p = rotateX(v, angleB * 1.5 + tiltX);
      p = rotateY(p, angleA + tiltY);
      return project(p, centerIco.x, centerIco.y, 450, 480);
    });
    ctx.strokeStyle = 'rgba(168, 85, 247, 0.14)';
    ctx.beginPath();
    rotRingVerts.forEach((p, idx) => {
      if (idx === 0) ctx.moveTo(p.x, p.y);
      else ctx.lineTo(p.x, p.y);
    });
    ctx.closePath();
    ctx.stroke();

    // --- D. Floating Knowledge Lattice Particles & Connections ---
    const cx = width / 2;
    const cy = height / 2;
    const projectedLattice = [];

    latticeNodes.forEach((node) => {
      node.x += node.vx;
      node.y += node.vy;
      node.z += node.vz;
      if (Math.abs(node.x) > 450) node.vx *= -1;
      if (Math.abs(node.y) > 350) node.vy *= -1;
      if (Math.abs(node.z) > 300) node.vz *= -1;

      let p = rotateX(node, tiltX * 0.5);
      p = rotateY(p, tiltY * 0.5);
      const proj = project(p, cx, cy, 450, 600);
      proj.radius = node.radius;
      projectedLattice.push(proj);
    });

    // Draw connecting edges
    for (let i = 0; i < projectedLattice.length; i++) {
      for (let j = i + 1; j < projectedLattice.length; j++) {
        const p1 = projectedLattice[i];
        const p2 = projectedLattice[j];
        const dx = p1.x - p2.x;
        const dy = p1.y - p2.y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < 110) {
          const alpha = (1 - dist / 110) * 0.12;
          ctx.strokeStyle = `rgba(79, 70, 229, ${alpha})`;
          ctx.lineWidth = 0.8;
          ctx.beginPath();
          ctx.moveTo(p1.x, p1.y);
          ctx.lineTo(p2.x, p2.y);
          ctx.stroke();
        }
      }
    }

    // Draw particle beads
    projectedLattice.forEach((p) => {
      const alpha = 0.15 + (p.scale * 0.2);
      ctx.fillStyle = `rgba(79, 70, 229, ${alpha})`;
      ctx.beginPath();
      ctx.arc(p.x, p.y, Math.max(1, p.radius * p.scale), 0, Math.PI * 2);
      ctx.fill();
    });

    requestAnimationFrame(renderLoop);
  }

  requestAnimationFrame(renderLoop);
}

// ============================================================================
// 4. AUTHENTICATION & SESSION MANAGEMENT
// ============================================================================
function getAuthHeaders(extra = {}) {
  const headers = { ...extra };
  if (state.token) {
    headers['Authorization'] = `Bearer ${state.token}`;
    headers['X-Auth-Token'] = state.token;
  }
  return headers;
}

document.addEventListener('DOMContentLoaded', async () => {
  init3DBackground();
  setupEventListeners();
  await checkExistingSession();
});

function setupEventListeners() {
  // Auth Mode Tabs (Sign In vs Create Account)
  modeSignInTab.addEventListener('click', () => switchAuthMode('login'));
  modeRegisterTab.addEventListener('click', () => switchAuthMode('register'));

  // Role Selector Toggle
  roleStudentToggle.addEventListener('click', () => setAuthRole('student'));
  roleTeacherToggle.addEventListener('click', () => setAuthRole('teacher'));

  // 1-Click Demo Evaluation Account Buttons
  const demoStudentBtn = document.getElementById('demoStudentBtn');
  const demoTeacherBtn = document.getElementById('demoTeacherBtn');
  if (demoStudentBtn) {
    demoStudentBtn.addEventListener('click', () => {
      switchAuthMode('login');
      setAuthRole('student');
      authUsername.value = 'student@academy.edu';
      authPassword.value = 'student123';
      hideAuthAlert();
    });
  }
  if (demoTeacherBtn) {
    demoTeacherBtn.addEventListener('click', () => {
      switchAuthMode('login');
      setAuthRole('teacher');
      authUsername.value = 'educator@academy.edu';
      authPassword.value = 'teacher123';
      hideAuthAlert();
    });
  }

  // Form Submit
  authForm.addEventListener('submit', handleAuthSubmit);
  authSubmitBtn.addEventListener('click', handleAuthSubmit);

  // Global Sign Out
  globalSignOutBtn.addEventListener('click', handleSignOut);

  // Nav Refresh Analytics
  if (navRefreshBtn) {
    navRefreshBtn.addEventListener('click', loadTeacherAnalytics);
  }

  // Student Agency Modality Cards
  modalityCards.forEach((btn) => {
    btn.addEventListener('click', () => {
      modalityCards.forEach((b) => b.classList.remove('active'));
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

  // Diagnostic Modal Close
  modalCloseBtn.addEventListener('click', () => explainModal.classList.add('hidden'));
  explainModal.addEventListener('click', (e) => {
    if (e.target === explainModal) explainModal.classList.add('hidden');
  });
}

function switchAuthMode(mode) {
  state.authMode = mode;
  hideAuthAlert();
  if (mode === 'login') {
    modeSignInTab.classList.add('active');
    modeRegisterTab.classList.remove('active');
    authNameFieldGroup.classList.add('hidden');
    authSchoolFieldGroup.classList.add('hidden');
    authSubmitBtn.textContent = 'Sign In to Portal';
    authUsernameLabel.textContent = 'Institutional Email or Username';
    authFullName.required = false;
  } else {
    modeRegisterTab.classList.add('active');
    modeSignInTab.classList.remove('active');
    authNameFieldGroup.classList.remove('hidden');
    authSchoolFieldGroup.classList.remove('hidden');
    authSubmitBtn.textContent = 'Create My Account';
    authUsernameLabel.textContent = 'Choose Username or Email';
    authFullName.required = true;
  }
}

function setAuthRole(role) {
  state.authRole = role;
  if (role === 'student') {
    roleStudentToggle.classList.add('active');
    roleTeacherToggle.classList.remove('active');
    authUsername.placeholder = 'student@academy.edu or username';
  } else {
    roleTeacherToggle.classList.add('active');
    roleStudentToggle.classList.remove('active');
    authUsername.placeholder = 'educator@academy.edu or username';
  }
}

function showAuthAlert(message, type = 'error') {
  authAlertBanner.textContent = message;
  authAlertBanner.className = `alert-banner ${type}`;
  authAlertBanner.classList.remove('hidden');
}

function hideAuthAlert() {
  authAlertBanner.classList.add('hidden');
  authAlertBanner.textContent = '';
}

async function handleAuthSubmit() {
  hideAuthAlert();
  const username = authUsername.value.trim();
  const password = authPassword.value.trim();

  if (!username) {
    showAuthAlert('Please enter your institutional email or username.');
    return;
  }
  if (!password) {
    showAuthAlert('Please enter your password.');
    return;
  }

  authSubmitBtn.disabled = true;
  authSubmitBtn.textContent = state.authMode === 'login' ? 'Authenticating...' : 'Creating Account...';

  try {
    if (state.authMode === 'register') {
      const fullName = authFullName.value.trim();
      const schoolName = authSchoolName.value.trim() || 'IRONCLAD Academy';

      const res = await fetch('/api/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username,
          password,
          name: fullName || username,
          role: state.authRole,
          school_name: schoolName,
        }),
      });

      const contentType = res.headers.get('content-type') || '';
      const data = contentType.includes('application/json') ? await res.json() : {};
      if (!res.ok) {
        throw new Error(data.error || `Registration failed (Status ${res.status}).`);
      }

      state.token = data.token;
      state.user = data.user;
      localStorage.setItem('ironclad_token', data.token);
      routeAuthenticatedUser();
    } else {
      // Login Mode
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username,
          password,
          role: state.authRole,
        }),
      });

      const contentType = res.headers.get('content-type') || '';
      const data = contentType.includes('application/json') ? await res.json() : {};
      if (!res.ok) {
        throw new Error(data.error || `Authentication failed (Status ${res.status}).`);
      }

      state.token = data.token;
      state.user = data.user;
      localStorage.setItem('ironclad_token', data.token);
      routeAuthenticatedUser();
    }
  } catch (err) {
    showAuthAlert(err.message, 'error');
  } finally {
    authSubmitBtn.disabled = false;
    authSubmitBtn.textContent = state.authMode === 'login' ? 'Sign In to Portal' : 'Create My Account';
  }
}

async function checkExistingSession() {
  if (!state.token) {
    showView('auth');
    return;
  }

  try {
    const res = await fetch('/api/auth/me', {
      headers: getAuthHeaders(),
    });
    if (!res.ok) throw new Error('Session expired');
    const contentType = res.headers.get('content-type') || '';
    if (!contentType.includes('application/json')) {
      throw new Error('Invalid server response');
    }
    const data = await res.json();
    if (!data.user) throw new Error('Invalid user payload');
    state.user = data.user;
    routeAuthenticatedUser();
  } catch (err) {
    console.warn('Session check:', err.message);
    state.token = null;
    state.user = null;
    localStorage.removeItem('ironclad_token');
    showView('auth');
  }
}

async function handleSignOut() {
  if (state.token) {
    try {
      await fetch('/api/auth/logout', {
        method: 'POST',
        headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
      });
    } catch (e) {}
  }
  state.token = null;
  state.user = null;
  localStorage.removeItem('ironclad_token');
  showView('auth');
}

function showView(viewName) {
  authScreen.classList.remove('active');
  studentPortal.classList.remove('active');
  teacherPortal.classList.remove('active');

  if (viewName === 'auth') {
    authScreen.classList.add('active');
    appNav.classList.add('hidden');
  } else if (viewName === 'student') {
    studentPortal.classList.add('active');
    appNav.classList.remove('hidden');
    navRoleTag.textContent = 'Student Studio';
    navRefreshBtn.classList.add('hidden');
    navStudentStreak.classList.remove('hidden');
  } else if (viewName === 'teacher') {
    teacherPortal.classList.add('active');
    appNav.classList.remove('hidden');
    navRoleTag.textContent = 'Educator Center';
    navRefreshBtn.classList.remove('hidden');
    navStudentStreak.classList.add('hidden');
  }
}

function routeAuthenticatedUser() {
  if (!state.user) {
    showView('auth');
    return;
  }

  // Update Navbar Profile
  const name = state.user.name || state.user.username;
  navUserName.textContent = name;
  navUserRole.textContent = state.user.role === 'teacher' ? 'Educator' : 'Student Candidate';
  navUserAvatar.textContent = name.charAt(0).toUpperCase();

  if (state.user.role === 'teacher') {
    showView('teacher');
    loadCurriculumData().then(() => {
      loadTeacherAnalytics();
    });
  } else {
    showView('student');
    loadCurriculumData().then(() => {
      initializeStudentStudio();
    });
  }
}

// ============================================================================
// 5. CURRICULUM GRAPH DATA LOADER
// ============================================================================
async function loadCurriculumData() {
  try {
    const res = await fetch(`/api/curriculum?domain=${state.domain}`, {
      headers: getAuthHeaders(),
    });
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
// 6. STUDENT PORTAL CONTROLLER
// ============================================================================
async function initializeStudentStudio() {
  // Populate syllabus dropdown
  studentTopicSelect.innerHTML = state.nodes
    .map((n) => `<option value="${n.id}">${n.name}</option>`)
    .join('');

  if (state.nodes.length > 0) {
    studentTopicSelect.value = state.nodes[0].id;
  }

  await updateStudentTopicMasteryDisplay();
  await generateStudentLesson();
}

async function updateStudentTopicMasteryDisplay() {
  const conceptId = studentTopicSelect.value;
  const studentId = state.user?.student_id || `s_${state.user?.username}`;

  try {
    const res = await fetch(`/api/student/${studentId}`, {
      headers: getAuthHeaders(),
    });
    if (res.ok) {
      const student = await res.json();
      const mastery = student.concept_mastery ? student.concept_mastery[conceptId] : null;
      const pct = mastery !== undefined && mastery !== null ? Math.round(mastery * 100) : 0;

      topicMasteryScore.textContent = `${pct}%`;
      topicMasteryFill.style.width = `${pct}%`;

      if (pct >= 80) {
        topicMasteryFill.style.background = '#059669';
      } else if (pct >= 50) {
        topicMasteryFill.style.background = '#d97706';
      } else {
        topicMasteryFill.style.background = '#4f46e5';
      }

      if (student.streak_correct > 0) {
        streakCountText.textContent = `${student.streak_correct} Correct in a Row`;
      } else {
        streakCountText.textContent = 'Active Learning';
      }
    }
  } catch (err) {
    console.error('Failed to load student mastery:', err);
  }
}

async function updateStudentModalityPreference(modality) {
  const studentId = state.user?.student_id || `s_${state.user?.username}`;
  try {
    await fetch('/api/student/preference', {
      method: 'POST',
      headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ student_id: studentId, modality }),
    });
  } catch (err) {
    console.error('Failed to save modality preference:', err);
  }
}

async function generateStudentLesson() {
  const studentId = state.user?.student_id || `s_${state.user?.username}`;
  const conceptId = studentTopicSelect.value;
  if (!conceptId) return;

  studentSynthesizeBtn.disabled = true;
  studentSynthesizeBtn.innerHTML = `
    <svg class="svg-icon sm" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>
    </svg>
    <span>Synthesizing Tailored Lesson...</span>
  `;

  try {
    const res = await fetch('/api/lesson', {
      method: 'POST',
      headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({
        student_id: studentId,
        concept_id: conceptId,
        domain: state.domain,
        modality: state.activeModality,
      }),
    });

    const lesson = await res.json();

    if (!res.ok || lesson.error) {
      throw new Error(lesson.error || `Server returned ${res.status}`);
    }

    state.currentLesson = lesson;

    studentLessonTitle.textContent = lesson.concept_name || 'Lesson';
    const cleanModality = (lesson.modality || state.activeModality || 'worked_examples').replace(/_/g, ' ').toUpperCase();
    studentLessonTag.textContent = `NCERT SEQUENCE &bull; ${cleanModality}`;

    const explanationHtml = (lesson.explanation || 'No explanation available.').replace(/\n\n/g, '<br><br>');
    const workedExampleHtml = lesson.worked_example || 'No worked example available.';
    const guidedExerciseHtml = lesson.guided_exercise || 'No guided exercise available.';

    studentLessonBody.innerHTML = `
      ${
        lesson.socratic_scaffolding
          ? `<div class="pedagogy-scaffold-banner">
              <strong>Pedagogical Scaffolding:</strong> ${lesson.socratic_scaffolding}
             </div>`
          : ''
      }
      <div style="margin-bottom: 1.25rem;">
        ${explanationHtml}
      </div>

      <div class="lesson-box-section">
        <div class="lesson-box-title">Step-by-Step Worked Example</div>
        <div style="white-space: pre-wrap; font-size: 0.9rem; color: #1e293b;">${workedExampleHtml}</div>
      </div>

      <div class="lesson-box-section guided">
        <div class="lesson-box-title">Guided Socratic Practice</div>
        <div style="font-size: 0.9rem; color: #1e293b;">${guidedExerciseHtml}</div>
      </div>
    `;

    renderAssessmentItem(lesson.assessment_items || []);
  } catch (err) {
    console.error('Failed to generate lesson:', err);
    studentLessonBody.innerHTML = `<p style="color: var(--rose);">Could not synthesize lesson: ${err.message}</p>`;
  } finally {
    studentSynthesizeBtn.disabled = false;
    studentSynthesizeBtn.innerHTML = `
      <svg class="svg-icon sm" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="m12 3-1.9 5.8a2 2 0 0 1-1.3 1.3L3 12l5.8 1.9a2 2 0 0 1 1.3 1.3L12 21l1.9-5.8a2 2 0 0 1 1.3-1.3L21 12l-5.8-1.9a2 2 0 0 1-1.3-1.3Z"/>
      </svg>
      <span>Synthesize Tailored Lesson</span>
    `;
  }
}

function renderAssessmentItem(items) {
  studentFeedbackBox.classList.add('hidden');
  if (!items || items.length === 0) {
    studentAssessmentContent.innerHTML = '<p class="placeholder-text">No practice questions available for this unit.</p>';
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
      <input type="text" id="freeformAnswerInput" class="styled-input" placeholder="Type your answer...">
    `;

  studentAssessmentContent.innerHTML = `
    <div class="assessment-question-text">${q.question}</div>
    <div class="assessment-options-list">
      ${optionsHtml}
    </div>
    <button id="submitAssessmentBtn" class="btn-primary full-width-btn" style="margin-top: 1rem;">
      <span>Submit Answer for Socratic Evaluation</span>
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
    alert('Please select or enter an answer before submitting.');
    return;
  }

  const latencySec = (Date.now() - (state.assessmentStartTime || Date.now())) / 1000;
  const studentId = state.user?.student_id || `s_${state.user?.username}`;
  const conceptId = studentTopicSelect.value;

  const submitBtn = document.getElementById('submitAssessmentBtn');
  submitBtn.disabled = true;
  submitBtn.textContent = 'Evaluating Socratic Feedback...';

  try {
    const res = await fetch('/api/assess', {
      method: 'POST',
      headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
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

    studentFeedbackBox.className = `feedback-card ${result.is_correct ? 'correct' : 'socratic'}`;
    studentFeedbackBox.innerHTML = `
      <div class="feedback-title-row">
        <svg class="svg-icon sm" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          ${
            result.is_correct
              ? '<polyline points="20 6 9 17 4 12"/>'
              : '<circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>'
          }
        </svg>
        <span>${result.is_correct ? 'Correct! Mastery Progress Recorded' : 'Socratic Pedagogical Guidance'}</span>
      </div>
      <div class="feedback-message-text">${result.socratic_feedback}</div>
      ${
        result.prerequisite_gap_detected
          ? `
        <div class="prereq-alert-banner">
          <strong>Upstream Prerequisite Deficit Detected:</strong> <code>${result.prerequisite_gap_detected}</code><br>
          Our knowledge graph identified that reviewing this prerequisite will directly unlock comprehension of this chapter.
        </div>
      `
          : ''
      }
    `;

    studentFeedbackBox.classList.remove('hidden');
    await updateStudentTopicMasteryDisplay();
  } catch (err) {
    console.error('Failed to submit assessment:', err);
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = 'Submit Answer for Socratic Evaluation';
  }
}

// ============================================================================
// 7. EDUCATOR PORTAL CONTROLLER
// ============================================================================
async function loadTeacherAnalytics() {
  try {
    const summaryRes = await fetch(`/api/class-summary?domain=${state.domain}`, {
      headers: getAuthHeaders(),
    });
    const summary = await summaryRes.json();

    kpiTotalStudents.textContent = summary.total_students || 0;
    kpiAvgMastery.textContent = `${summary.average_mastery_pct || 0.0}%`;
    kpiAtRiskCount.textContent = summary.students_requiring_intervention || 0;
    kpiUnitsCount.textContent = `${state.nodes.length} Units`;

    renderTeacherAlerts(summary.active_alerts || []);
    renderTeacherDAG();

    const studentsRes = await fetch(`/api/students?domain=${state.domain}`, {
      headers: getAuthHeaders(),
    });
    const students = await studentsRes.json();
    renderTeacherStudentsTable(students);
  } catch (err) {
    console.error('Failed to load teacher analytics:', err);
  }
}

function renderTeacherAlerts(alerts) {
  if (!alerts || alerts.length === 0) {
    teacherAlertsContainer.innerHTML = `
      <div style="grid-column: 1 / -1; padding: 1.5rem; text-align: center; color: var(--text-muted); background: var(--bg-subtle); border-radius: var(--radius-md);">
        All active candidates are currently meeting mastery benchmarks. No interventions required.
      </div>
    `;
    return;
  }

  teacherAlertsContainer.innerHTML = alerts
    .map((alert) => {
      const isHigh = alert.severity === 'high';
      const cardClass = isHigh ? 'alert-card' : 'alert-card medium';
      const tagClass = isHigh ? 'tag-badge rose' : 'tag-badge amber';

      return `
        <div class="${cardClass}">
          <div class="alert-card-top">
            <span class="alert-student-name">${alert.student_name}</span>
            <span class="${tagClass}">${alert.severity.toUpperCase()} PRIORITY</span>
          </div>
          <div class="alert-body-text">${alert.message}</div>
          <div class="alert-actions-bar">
            <button class="btn-secondary" onclick="openDiagnosticModal('${alert.student_id}', '${alert.concept_id}')">
              <svg class="svg-icon sm" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
              </svg>
              <span>Inspect Diagnostic Evidence</span>
            </button>
            <button class="btn-outline-resolve" onclick="resolveAlert('${alert.alert_id}')">
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
      headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ alert_id: alertId }),
    });
    loadTeacherAnalytics();
  } catch (err) {
    console.error('Failed to resolve alert:', err);
  }
};

window.openDiagnosticModal = async function (studentId, conceptId) {
  try {
    const res = await fetch(`/api/explain/${studentId}?domain=${state.domain}&concept=${conceptId || ''}`, {
      headers: getAuthHeaders(),
    });
    const expl = await res.json();

    modalStudentTitle.textContent = `Diagnostic Intervention Rationale: ${expl.student_name}`;
    modalBody.innerHTML = `
      <div>
        <strong>Target Chapter:</strong> ${expl.target_concept}<br>
        <strong>Struggle Classification:</strong> <span class="tag-badge rose">${expl.struggle_type}</span>
      </div>

      <div class="modal-highlight-box">
        <strong style="color: var(--indigo);">Recommended Educator Action:</strong>
        <p style="margin-top: 0.35rem; color: #1e293b;">${expl.recommended_action}</p>
        ${
          expl.prerequisite_root_cause
            ? `<div style="margin-top: 0.5rem; font-size: 0.8rem; color: #b91c1c;">
                Prerequisite Deficit Identified: <strong>${expl.prerequisite_root_cause}</strong>
               </div>`
            : ''
        }
      </div>

      <div>
        <strong>Automated Diagnostic Chain &amp; Evidence Points:</strong>
        <ul class="evidence-ul">
          ${expl.evidence_points.map((pt) => `<li>${pt}</li>`).join('')}
        </ul>
      </div>

      <div class="modal-pedagogy-box">
        <strong style="color: var(--emerald);">Suggested Teaching Strategy:</strong>
        <p style="margin-top: 0.35rem; color: #064e3b;">${expl.suggested_teaching_strategy}</p>
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
  const height = 460;

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
    <marker id="teacherArrow" markerWidth="8" markerHeight="6" refX="22" refY="3" orient="auto">
      <polygon points="0 0, 8 3, 0 6" fill="#4f46e5" opacity="0.7" />
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

      path.setAttribute('d', `M ${sourcePos.x} ${sourcePos.y} C ${cx1} ${cy1}, ${cx2} ${cy2}, ${targetPos.x} ${targetPos.y}`);
      path.setAttribute('fill', 'none');
      path.setAttribute('stroke', 'rgba(79, 70, 229, 0.35)');
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
    circle.setAttribute('r', '17');
    circle.setAttribute('fill', '#ffffff');
    circle.setAttribute('stroke', '#4f46e5');
    circle.setAttribute('stroke-width', '2.5');
    group.appendChild(circle);

    const label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    label.setAttribute('x', x);
    label.setAttribute('y', y + 30);
    label.setAttribute('text-anchor', 'middle');
    label.setAttribute('fill', '#334155');
    label.setAttribute('font-size', '10px');
    label.setAttribute('font-weight', '700');
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
    <div style="border-bottom: 1px solid var(--border-subtle); padding-bottom: 0.75rem; margin-bottom: 0.85rem;">
      <span class="tag-badge indigo">NCERT Difficulty Level ${concept.difficulty}/5</span>
      <h4 style="color: var(--text-primary); font-size: 1.05rem; margin-top: 0.35rem;">${concept.name}</h4>
    </div>
    
    <p style="font-size: 0.85rem; color: var(--text-secondary); line-height: 1.5; margin-bottom: 0.85rem;">${concept.description}</p>
    
    <div style="margin-bottom: 0.85rem;">
      <strong style="font-size: 0.75rem; text-transform: uppercase; color: var(--indigo); letter-spacing: 0.05em;">Upstream Prerequisites:</strong>
      ${
        concept.prerequisites && concept.prerequisites.length > 0
          ? `<ul class="evidence-ul">${concept.prerequisites.map((p) => `<li><code>${p}</code></li>`).join('')}</ul>`
          : '<p style="font-size: 0.8rem; color: var(--text-muted); margin-top: 0.25rem;">None (Foundational Chapter)</p>'
      }
    </div>

    <div style="margin-bottom: 0.85rem;">
      <strong style="font-size: 0.75rem; text-transform: uppercase; color: var(--indigo); letter-spacing: 0.05em;">Curricular Objectives:</strong>
      <ul class="evidence-ul">
        ${concept.learning_objectives.map((obj) => `<li>${obj}</li>`).join('')}
      </ul>
    </div>

    ${
      concept.real_world_context
        ? `
      <div style="background: var(--bg-subtle); padding: 0.85rem; border-radius: var(--radius-sm);">
        <strong style="font-size: 0.75rem; color: var(--cyan); text-transform: uppercase;">Real-World Practical Context:</strong>
        <p style="font-size: 0.8rem; color: var(--text-secondary); margin-top: 0.25rem;">${concept.real_world_context}</p>
      </div>`
        : ''
    }
  `;
}

function renderTeacherStudentsTable(students) {
  if (!students || students.length === 0) {
    teacherStudentsTable.innerHTML = `
      <tr>
        <td colspan="6" class="empty-roster-banner">
          No students registered in this cohort yet. Once learners create accounts and take lessons, their progress will appear here.
        </td>
      </tr>
    `;
    return;
  }

  teacherStudentsTable.innerHTML = students
    .map((s) => {
      let statusHtml = '<span class="tag-badge emerald">Mastered</span>';
      if (s.active_struggle) {
        statusHtml = `<span class="tag-badge rose">Struggle: ${s.active_struggle.replace('c10_', '')}</span>`;
      } else if (s.learning_pace === 'needs_scaffolding') {
        statusHtml = '<span class="tag-badge amber">Needs Scaffolding</span>';
      }

      return `
        <tr>
          <td>
            <strong style="color: var(--text-primary);">${s.name}</strong><br>
            <small style="color: var(--text-muted);">${s.student_id}</small>
          </td>
          <td><span style="font-family: var(--font-mono); font-size: 0.8rem;">${s.learning_pace}</span></td>
          <td><span class="tag-badge indigo">${s.preferred_modality}</span></td>
          <td><strong>${s.correct_assessments}</strong> / ${s.total_assessments}</td>
          <td>${statusHtml}</td>
          <td>
            <button class="btn-secondary" onclick="openDiagnosticModal('${s.student_id}', '${s.active_struggle || ''}')">
              Explain Rationale
            </button>
          </td>
        </tr>
      `;
    })
    .join('');
}
