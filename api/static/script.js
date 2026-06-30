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
const errorMessage = document.getElementById('errorMessage');
const sidebar = document.getElementById('sidebar');

let selectedFiles = [];

// --- User Identity Management ---
function initUser() {
    const savedName = localStorage.getItem('talentflow_username');
    if (savedName) {
        setProfileName(savedName);
    } else {
        openSettings();
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
    
    if (resultsContainer.style.display === 'block' || resultsContainer.style.display === '') {
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
}

if (fileInput) {
    fileInput.addEventListener('change', (e) => {
        handleFiles(e.target.files);
    });
}

function handleFiles(files) {
    // Append to existing instead of replacing if multiple drops
    const newFiles = Array.from(files);
    selectedFiles = [...selectedFiles, ...newFiles];
    updateFileList();
    if (selectedFiles.length > 0) {
        processBtn.style.display = 'flex';
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

    errorMessage.style.display = 'none';
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
        errorMessage.textContent = 'Error: ' + error.message;
        errorMessage.style.display = 'block';
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
                <span class="info-icon">📧</span>
                <span>${emailStr}</span>
                
                <span class="info-icon">📱</span>
                <span>${phoneStr}</span>

                <span class="info-icon">📍</span>
                <span>${location}</span>
            </div>

            <div>
                <div style="font-size:0.85rem; margin-bottom:0.5rem; color:var(--text-muted); font-weight: 600; letter-spacing: 0.5px;">TOP SKILLS</div>
                <div class="skills-container">${skillsHtml}</div>
            </div>

            <div class="card-actions">
                <button class="btn-outline" onclick="toggleRawData(${idx})">Inspect JSON</button>
            </div>
            <pre class="raw-json" id="raw-json-${idx}">${escapeHtml(JSON.stringify(profile, null, 2))}</pre>
        `;
        
        profileGrid.appendChild(card);
    });
}

function toggleRawData(idx) {
    const rawJson = document.getElementById(`raw-json-${idx}`);
    const btn = rawJson.previousElementSibling.querySelector('button');
    if (rawJson.style.display === 'block') {
        rawJson.style.display = 'none';
        btn.textContent = 'Inspect JSON';
    } else {
        rawJson.style.display = 'block';
        btn.textContent = 'Hide JSON';
    }
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    initUser();
    fetchSamplesList();
});
