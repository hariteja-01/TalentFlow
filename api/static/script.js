// --- Utility Functions ---
function escapeHtml(unsafe) {
    if (typeof unsafe !== 'string') return unsafe;
    return unsafe
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

// --- DOM Elements ---
const nameModal = document.getElementById('nameModal');
const userNameInput = document.getElementById('userNameInput');
const sidebarUserName = document.getElementById('sidebarUserName');
const sidebarAvatarInitials = document.getElementById('sidebarAvatarInitials');
const sampleSelect = document.getElementById('sampleSelect');
const dropzone = document.getElementById('dropzone');
const fileInput = document.getElementById('fileInput');
const fileList = document.getElementById('fileList');
const processBtn = document.getElementById('processBtn');
const loadingContainer = document.getElementById('loadingContainer');
const resultsContainer = document.getElementById('resultsContainer');
const profileGrid = document.getElementById('profileGrid');
const errorBanner = document.getElementById('errorBanner');
const errorTitle = document.getElementById('errorTitle');
const errorMessage = document.getElementById('errorMessage');
const sidebar = document.getElementById('sidebar');
const sidebarToggleBtn = document.getElementById('sidebarToggleBtn');

let selectedFiles = [];

// Close error banner
function closeError() {
    errorBanner.style.display = 'none';
}

// --- User Identity Management & Sidebar ---
function initApp() {
    // User Name
    const savedName = localStorage.getItem('talentflow_username');
    if (savedName) {
        setProfileName(savedName);
    } else {
        openSettings();
    }

    // Sidebar state
    const sidebarCollapsed = localStorage.getItem('talentflow_sidebar_collapsed');
    if (sidebarCollapsed === 'true' && sidebar) {
        sidebar.classList.add('collapsed');
        sidebar.setAttribute('aria-expanded', 'false');
    }

    if (sidebarToggleBtn && sidebar) {
        sidebarToggleBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            sidebar.classList.toggle('collapsed');
            const isCollapsed = sidebar.classList.contains('collapsed');
            localStorage.setItem('talentflow_sidebar_collapsed', isCollapsed);
            sidebar.setAttribute('aria-expanded', !isCollapsed);
        });
    }
}

function openSettings() {
    nameModal.classList.add('active');
    userNameInput.value = localStorage.getItem('talentflow_username') || '';
    userNameInput.focus();
}

function saveUserName() {
    let name = userNameInput.value.trim();
    if (!name) name = "Anonymous User";
    localStorage.setItem('talentflow_username', name);
    setProfileName(name);
    nameModal.classList.remove('active');
}

function setProfileName(name) {
    sidebarUserName.textContent = name;
    const initials = name.split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase();
    sidebarAvatarInitials.textContent = initials || 'U';
}

if (userNameInput) {
    userNameInput.addEventListener('keypress', function (e) {
        if (e.key === 'Enter') saveUserName();
    });
}

// --- Mobile Sidebar Toggle ---
function toggleSidebar() {
    sidebar.classList.toggle('open');
}

// Close sidebar when clicking outside on mobile
document.addEventListener('click', (e) => {
    if (window.innerWidth <= 768 && sidebar.classList.contains('open')) {
        if (!sidebar.contains(e.target) && !e.target.closest('.mobile-toggle')) {
            sidebar.classList.remove('open');
        }
    }
});

// --- Sample Loader Logic ---
async function fetchSamplesList() {
    try {
        const response = await fetch('/api/samples');
        if (response.ok) {
            const data = await response.json();
            data.samples.forEach(samplePath => {
                const opt = document.createElement('option');
                opt.value = samplePath;
                const folder = samplePath.split('/').length > 1 ? samplePath.split('/')[0] : 'root';
                opt.textContent = `${samplePath.split('/').pop()} (${folder})`;
                sampleSelect.appendChild(opt);
            });
        }
    } catch (err) {
        console.error("Failed to load sample list", err);
    }
}

async function loadSampleFile() {
    const filepath = sampleSelect.value;
    if (!filepath) return;
    
    if (resultsContainer.style.display !== 'none' && resultsContainer.style.display !== '') {
        resetPipeline();
    }
    
    try {
        const response = await fetch(`/api/samples/${filepath}`);
        if (!response.ok) throw new Error("Failed to fetch sample");
        
        const blob = await response.blob();
        const filename = filepath.split('/').pop();
        const file = new File([blob], filename, { type: blob.type || 'text/plain' });
        
        handleFiles([file]);
        processFiles();
    } catch (err) {
        alert("Error loading sample: " + err.message);
    }
}

// --- File Upload & Pipeline Logic ---
if (dropzone) {
    dropzone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropzone.classList.add('dragover');
    });

    dropzone.addEventListener('dragleave', () => {
        dropzone.classList.remove('dragover');
    });

    dropzone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropzone.classList.remove('dragover');
        handleFiles(e.dataTransfer.files);
    });
    
    // Proper click and keydown handlers avoiding event bubbling loops
    dropzone.addEventListener('click', (e) => {
        if (e.target !== fileInput && e.target !== fileList && !fileList.contains(e.target)) {
            fileInput.click();
        }
    });

    dropzone.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            fileInput.click();
        }
    });
}

if (fileInput) {
    fileInput.addEventListener('change', (e) => {
        handleFiles(e.target.files);
    });
}

function handleFiles(files) {
    if (!files || files.length === 0) return;
    
    const newFiles = Array.from(files);
    selectedFiles = [...selectedFiles, ...newFiles];
    updateFileList();
    
    // Clear input so same file can be uploaded again
    if (fileInput) {
        fileInput.value = '';
    }

    if (selectedFiles.length > 0) {
        processBtn.style.display = 'none'; // Auto process, so we hide the button
        processFiles(); // Instantly process!
    } else {
        processBtn.style.display = 'none';
    }
}

function removeFile(index) {
    selectedFiles.splice(index, 1);
    updateFileList();
    if (selectedFiles.length === 0) {
        processBtn.style.display = 'none';
    }
}

function updateFileList() {
    fileList.innerHTML = '';
    selectedFiles.forEach((file, idx) => {
        const item = document.createElement('div');
        item.className = 'file-item';
        item.innerHTML = `
            <div>
                <span style="font-weight:500; color:#e2e8f0; margin-right: 1rem;">📁 ${escapeHtml(file.name)}</span> 
                <span style="color:var(--text-muted); font-size: 0.85rem;">${(file.size / 1024).toFixed(1)} KB</span>
            </div>
            <button class="btn-outline" style="padding: 0.25rem 0.5rem; font-size: 0.8rem; border: none;" onclick="removeFile(${idx})">❌</button>
        `;
        fileList.appendChild(item);
    });
}

function resetPipeline() {
    resultsContainer.style.display = 'none';
    dropzone.style.display = 'flex';
    selectedFiles = [];
    fileInput.value = '';
    updateFileList();
    processBtn.style.display = 'none';
}

async function processFiles() {
    if (selectedFiles.length === 0) return;

    closeError();
    resultsContainer.style.display = 'none';
    dropzone.style.display = 'none';
    loadingContainer.style.display = 'flex';
    profileGrid.innerHTML = '';

    const formData = new FormData();
    selectedFiles.forEach(file => {
        formData.append('files', file);
    });

    try {
        const response = await fetch('/api/process', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || 'Failed to process files');
        }

        renderProfiles(data.profiles);
        loadingContainer.style.display = 'none';
        resultsContainer.style.display = 'block';
        
    } catch (error) {
        loadingContainer.style.display = 'none';
        dropzone.style.display = 'flex';
        
        let msg = error.message;
        if (msg.includes('Failed to fetch')) {
            msg = 'Server disconnected. Please ensure the API is running.';
        }
        
        errorTitle.textContent = 'Processing Failed';
        errorMessage.textContent = msg;
        errorBanner.style.display = 'flex';
    }
}

function renderProfiles(profiles) {
    if (profiles.length === 0) {
        profileGrid.innerHTML = '<p style="color:var(--text-muted)">No profiles were extracted.</p>';
        return;
    }

    profiles.forEach((profile, idx) => {
        const card = document.createElement('div');
        card.className = 'profile-card';
        
        const name = escapeHtml(profile.full_name || 'Unknown Candidate');
        const confScore = escapeHtml(profile.overall_confidence ? (profile.overall_confidence * 100).toFixed(0) : '0');
        const emails = profile.emails || [];
        const emailStr = escapeHtml(emails.length > 0 ? emails[0] : 'N/A');
        const phones = profile.phones || [];
        const phoneStr = escapeHtml(phones.length > 0 ? phones[0] : 'N/A');
        const location = escapeHtml(profile.location?.country || 'N/A');

        const skills = profile.skills || [];
        let skillsHtml = '';
        if (skills.length > 0) {
            skills.slice(0, 5).forEach(skill => {
                const skillName = typeof skill === 'object' ? skill.name : skill;
                skillsHtml += `<span class="skill-tag">${escapeHtml(skillName)}</span>`;
            });
            if (skills.length > 5) skillsHtml += `<span class="skill-tag" style="background:transparent; border-color:transparent">+${skills.length - 5}</span>`;
        } else {
            skillsHtml = '<span style="color:var(--text-muted);font-size:0.85rem">No skills</span>';
        }

        card.innerHTML = `
            <div class="card-header">
                <h3 class="candidate-name">${name}</h3>
                <div class="confidence-badge">
                    <span style="font-size: 1rem;">✨</span> ${confScore}% Match
                </div>
            </div>
            
            <div class="info-grid">
                <div class="info-item">
                    <span class="info-icon">📧</span>
                    <span class="info-text">${emailStr}</span>
                </div>
                <div class="info-item">
                    <span class="info-icon">📱</span>
                    <span class="info-text">${phoneStr}</span>
                </div>
                <div class="info-item">
                    <span class="info-icon">📍</span>
                    <span class="info-text">${location}</span>
                </div>
            </div>

            <div class="skills-section">
                <div class="section-label">TOP SKILLS</div>
                <div class="skills-container">${skillsHtml}</div>
            </div>

            <div class="card-actions">
                <button class="btn-outline btn-sm" onclick="toggleRawData(${idx})" aria-expanded="false">View JSON Profile</button>
            </div>
            <div class="raw-json-container" id="raw-json-${idx}">
                <div class="json-header">
                    <span>canonical_profile.json</span>
                    <button class="copy-btn" onclick="copyJson(${idx})" title="Copy to clipboard">📋 Copy</button>
                </div>
                <pre class="raw-json">${escapeHtml(JSON.stringify(profile, null, 2))}</pre>
            </div>
        `;
        
        profileGrid.appendChild(card);
    });
}

function toggleRawData(idx) {
    const container = document.getElementById(`raw-json-${idx}`);
    const btn = container.previousElementSibling.querySelector('button');
    
    if (container.classList.contains('active')) {
        container.classList.remove('active');
        btn.textContent = 'View JSON Profile';
        btn.setAttribute('aria-expanded', 'false');
    } else {
        container.classList.add('active');
        btn.textContent = 'Hide JSON Profile';
        btn.setAttribute('aria-expanded', 'true');
    }
}

function copyJson(idx) {
    const container = document.getElementById(`raw-json-${idx}`);
    const pre = container.querySelector('pre');
    navigator.clipboard.writeText(pre.textContent).then(() => {
        const btn = container.querySelector('.copy-btn');
        const origText = btn.textContent;
        btn.textContent = '✅ Copied!';
        setTimeout(() => btn.textContent = origText, 2000);
    }).catch(err => {
        console.error('Failed to copy text: ', err);
    });
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    initApp();
    fetchSamplesList();
    if (fileInput) {
        fileInput.value = '';
    }
});
