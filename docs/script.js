// ProAssist AI Landing Page Interactivity

document.addEventListener("DOMContentLoaded", () => {
  // ── 1. Waveform Visualizer Animation ─────────────────────────────────────
  const waveBars = document.querySelectorAll(".wave-bar");
  
  if (waveBars.length > 0) {
    let t = 0;
    setInterval(() => {
      t += 0.15;
      waveBars.forEach((bar, index) => {
        // Sine wave animation with phase shifts
        const val = Math.sin(t + index * 0.45) * 0.5 + 0.5;
        const height = Math.floor(8 + val * 34);
        bar.style.height = `${height}px`;
        
        // Color transition based on amplitude
        if (height > 30) {
          bar.style.backgroundColor = "var(--cyan)";
          bar.style.boxShadow = "0 0 8px var(--cyan-glow)";
        } else {
          bar.style.backgroundColor = "var(--pri)";
          bar.style.boxShadow = "none";
        }
      });
    }, 80);
  }

  // ── 2. Dynamic GitHub Repo & Download Router ──────────────────────────────
  const defaultRepo = "santhoshn-git/Proassist_AI_001";
  const repoInput = document.getElementById("github-repo-input");
  const updateBtn = document.getElementById("update-repo-btn");
  const downloadBtns = document.querySelectorAll(".btn-download-target");
  const githubLinks = document.querySelectorAll(".btn-github-target");
  const displayUrl = document.getElementById("display-download-url");

  function getSavedRepo() {
    return localStorage.getItem("proassist_github_repo") || defaultRepo;
  }

  function updateDownloadUrls(repo) {
    const cleanRepo = repo.trim().replace(/^https?:\/\/github\.com\//, "").replace(/\/$/, "");
    if (!cleanRepo) return;

    const downloadUrl = `https://github.com/${cleanRepo}/releases/latest/download/ProAssist_AI_Setup_v1.0.exe`;
    const repoUrl = `https://github.com/${cleanRepo}`;

    downloadBtns.forEach(btn => {
      btn.href = downloadUrl;
    });

    githubLinks.forEach(link => {
      link.href = repoUrl;
    });

    if (displayUrl) {
      displayUrl.textContent = downloadUrl;
      displayUrl.href = downloadUrl;
    }

    localStorage.setItem("proassist_github_repo", cleanRepo);
  }

  // Initialize with saved or default repo
  const initialRepo = getSavedRepo();
  if (repoInput) {
    repoInput.value = initialRepo;
  }
  updateDownloadUrls(initialRepo);

  if (updateBtn && repoInput) {
    updateBtn.addEventListener("click", () => {
      const userVal = repoInput.value.trim();
      if (userVal) {
        updateDownloadUrls(userVal);
        updateBtn.textContent = "✓ Updated!";
        setTimeout(() => {
          updateBtn.textContent = "Set Repository";
        }, 2000);
      }
    });
    
    repoInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        updateBtn.click();
      }
    });
  }

  // ── 3. Copy Link Helper ───────────────────────────────────────────────────
  const copyBtn = document.getElementById("copy-link-btn");
  if (copyBtn && displayUrl) {
    copyBtn.addEventListener("click", () => {
      navigator.clipboard.writeText(displayUrl.textContent).then(() => {
        const originalText = copyBtn.textContent;
        copyBtn.textContent = "Copied!";
        setTimeout(() => {
          copyBtn.textContent = originalText;
        }, 2000);
      });
    });
  }

  // ── 4. FAQ Accordion ──────────────────────────────────────────────────────
  const faqItems = document.querySelectorAll(".faq-item");
  faqItems.forEach(item => {
    const question = item.querySelector(".faq-q");
    if (question) {
      question.addEventListener("click", () => {
        const isActive = item.classList.contains("active");
        
        // Close all items
        faqItems.forEach(other => other.classList.remove("active"));
        
        // Toggle selected item
        if (!isActive) {
          item.classList.add("active");
        }
      });
    }
  });

  // ── 5. System Readout Telemetry Simulation ────────────────────────────────
  const cpuVal = document.getElementById("hud-cpu-val");
  const ramVal = document.getElementById("hud-ram-val");
  
  if (cpuVal && ramVal) {
    setInterval(() => {
      const randomCpu = (1.5 + Math.random() * 3.5).toFixed(1);
      const randomRam = (14.2 + Math.random() * 0.8).toFixed(1);
      cpuVal.textContent = `${randomCpu}%`;
      ramVal.textContent = `${randomRam} GB`;
    }, 2500);
  }
});
