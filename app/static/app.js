const state = {
  busy: false,
  sound: localStorage.getItem("xixi-sound") !== "off",
  history: [],
  currentSources: [],
  boardSync: null,
};

const audioPlayer = new Audio();
audioPlayer.preload = "auto";
audioPlayer.playsInline = true;
let speechRun = 0;
let speechRequestController = null;

const avatarMap = {
  wave: ["/assets/avatar-wave.png", "挥手问候的西西老师", "欢迎"],
  idle: ["/assets/avatar-idle.png", "等待提问的西西老师", "等待提问"],
  thinking: ["/assets/avatar-think.png", "正在思考的西西老师", "查找教材"],
  speaking: ["/assets/avatar-explain.png", "正在讲解的西西老师", "正在讲解"],
  point: ["/assets/avatar-point.png", "指向知识点的西西老师", "知识提示"],
  read: ["/assets/avatar-read.png", "阅读教材的西西老师", "阅读教材"],
  explain: ["/assets/avatar-explain.png", "双手讲解的西西老师", "讲解"],
  encourage: ["/assets/avatar-wave.png", "挥手鼓励学生的西西老师", "鼓励"],
  celebrate: ["/assets/avatar-wave.png", "挥手祝贺学生的西西老师", "祝贺"],
  correct: ["/assets/avatar-think.png", "认真检查代码的西西老师", "认真纠错"],
};

const footBounds = {
  wave: [155, 425], idle: [165, 465], thinking: [175, 465],
  speaking: [180, 445], point: [135, 415], read: [140, 455],
  explain: [180, 445], encourage: [155, 425], celebrate: [155, 425], correct: [175, 465],
};
const cleanedAvatars = new Map();
// Coordinates are in the original 640 x 740 PNG, not the stage/container.
// Pupil masks stay inside the glasses; aliases resolve through the image URL.
const faceLandmarks = {
  idle: { eyes: [[239, 212, 26, 36], [312, 215, 28, 36]], mouth: [275, 264, 84, 32] },
  wave: { eyes: [[220, 215, 30, 36], [306, 215, 28, 36]], mouth: [266, 266, 88, 34] },
  think: { eyes: [[281, 301, 32, 36], [366, 301, 30, 36]], mouth: [326, 350, 82, 32] },
  explain: { eyes: [[248, 225, 28, 36], [323, 226, 30, 36]], mouth: [284, 278, 84, 32] },
  point: { eyes: [[245, 212, 30, 36], [319, 209, 22, 32]], mouth: [283, 264, 86, 32] },
  read: { eyes: [[269, 233, 34, 38], [348, 230, 24, 34]], mouth: [309, 288, 80, 32] },
};
const facePatchCache = new Map();

function facePatch(image, bounds, eye) {
  const [cx, cy, width, height] = bounds;
  const source = document.createElement("canvas");
  source.width = image.naturalWidth;
  source.height = image.naturalHeight;
  const sourceContext = source.getContext("2d", { willReadFrequently: true });
  sourceContext.drawImage(image, 0, 0);
  const pixels = sourceContext.getImageData(cx - width / 2, cy - height / 2, width, height);
  const patch = document.createElement("canvas");
  patch.width = width;
  patch.height = height;
  const context = patch.getContext("2d");
  const result = context.createImageData(width, height);
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const index = (y * width + x) * 4;
      // Interpolate nearby skin across the pupil, or vertically across the smile.
      // Sample the middle of the lens to avoid smearing its upper/lower rim.
      const skinY = Math.max(Math.floor(height * .35), Math.min(y, Math.floor(height * .65)));
      const a = eye ? skinY * width * 4 : x * 4;
      const b = eye ? (skinY * width + width - 1) * 4 : ((height - 1) * width + x) * 4;
      const mix = eye ? x / (width - 1) : y / (height - 1);
      for (let channel = 0; channel < 3; channel++) {
        result.data[index + channel] = pixels.data[a + channel] * (1 - mix) + pixels.data[b + channel] * mix;
      }
      const radius = Math.hypot((x + .5 - width / 2) / (width / 2), (y + .5 - height / 2) / (height / 2));
      result.data[index + 3] = 255 * Math.min(1, Math.max(0, (1 - radius) / .15));
    }
  }
  context.putImageData(result, 0, 0);
  if (eye) {
    context.strokeStyle = "#352720";
    context.lineWidth = 2.4;
    context.lineCap = "round";
    context.beginPath();
    context.moveTo(width * .22, height * .52);
    context.quadraticCurveTo(width * .5, height * .69, width * .78, height * .52);
    context.stroke();
  }
  return patch.toDataURL();
}

function alignFaceOverlay() {
  const image = avatarFrames[activeAvatarFrame];
  const overlay = el("faceOverlay");
  if (!image.naturalWidth || !image.naturalHeight) return;
  const scale = Math.min(image.clientWidth / image.naturalWidth, image.clientHeight / image.naturalHeight);
  const width = image.naturalWidth * scale;
  const height = image.naturalHeight * scale;
  Object.assign(overlay.style, {
    width: `${width}px`, height: `${height}px`,
    left: `${(image.clientWidth - width) / 2}px`, top: `${image.clientHeight - height}px`,
  });
}

function syncFaceOverlay(image, src) {
  const overlay = el("faceOverlay");
  overlay.dataset.ready = "false";
  const key = src.split("avatar-")[1]?.replace(".png", "");
  const landmarks = faceLandmarks[key];
  if (!landmarks || !image.naturalWidth) return;
  try {
    const bounds = [...landmarks.eyes, landmarks.mouth];
    if (!facePatchCache.has(src)) facePatchCache.set(src, bounds.map((box, index) => facePatch(image, box, index < 2)));
    const patches = facePatchCache.get(src);
    [...overlay.children].forEach((part, index) => {
      const [x, y, width, height] = bounds[index];
      Object.assign(part.style, {
        left: `${(x - width / 2) / image.naturalWidth * 100}%`,
        top: `${(y - height / 2) / image.naturalHeight * 100}%`,
        width: `${width / image.naturalWidth * 100}%`, height: `${height / image.naturalHeight * 100}%`,
        backgroundImage: `url("${patches[index]}")`,
      });
    });
    overlay.dataset.pose = key;
    alignFaceOverlay();
    overlay.dataset.ready = "true";
  } catch { /* Leave effects hidden if an image cannot be sampled. */ }
}
const idleActionSpecs = [
  { name: "glance", weight: 30, duration: [1400, 2200], pose: "idle", label: "四处看看" },
  { name: "sway", weight: 25, duration: [1800, 2800], pose: "idle", label: "放松一下" },
  { name: "wave", weight: 20, duration: [1500, 2300], pose: "wave", label: "挥手问候" },
  { name: "sidestep", weight: 15, duration: [3000, 3000], pose: "idle", label: "短暂走动" },
  { name: "nod", weight: 10, duration: [1200, 1800], pose: "idle", label: "点头等待" },
];
const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
let idleDelayTimer;
let idleActionTimer;
let lastIdleAction = "";
let hasWalked = false;
let idleOffsetX = 0;
let activeAvatarFrame = 0;
let avatarTransitionRun = 0;
let gaitRun = 0;
let gaitFrame;
const gaitTextures = new WeakMap();

// Six alternating steps. Foot coordinates are in world space, so the support
// foot stays planted while the body travels. Both feet settle at the final root.
function gaitAt(progress, direction, distance = 72) {
  const p = Math.max(0, Math.min(1, progress));
  const step = Math.min(5, Math.floor(p * 6));
  const phase = p === 1 ? 1 : p * 6 - step;
  const stride = distance / 6;
  const root = p * distance;
  const smooth = phase * phase * (3 - 2 * phase);
  const feet = [0, 1].map((leg) => {
    let planted = 0;
    for (let previous = leg; previous < step; previous += 2) {
      planted = Math.min(6, previous + 2) * stride;
    }
    const swinging = step % 2 === leg;
    const target = Math.min(6, step + 2) * stride;
    const worldX = swinging ? planted + (target - planted) * smooth : planted;
    return { x: direction * (worldX - root), lift: swinging ? Math.sin(Math.PI * phase) * 13 : 0 };
  });
  return { root: direction * root, feet, turn: direction * Math.sin(Math.PI * p) };
}

function drawGait(image, gait) {
  const canvas = el("avatarGait");
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, 640, 740);
  // Keep the hips and head at a fixed height. A small horizontal shoulder turn
  // leads the legs, without mirroring the entire image or bouncing the body.
  ctx.save();
  ctx.translate(310, 584);
  ctx.transform(1 - Math.abs(gait.turn) * .025, 0, -gait.turn * .018, 1, 0, 0);
  ctx.drawImage(image, 0, 0, 640, 584, -310, -584, 640, 584);
  ctx.restore();
  // Inverse skinning with bilinear sampling keeps the trousers continuous;
  // drawing separate narrow strips would leave visible horizontal seams.
  if (!gaitTextures.has(image)) {
    const texture = document.createElement("canvas");
    texture.width = 640; texture.height = 740;
    const textureContext = texture.getContext("2d", { willReadFrequently: true });
    textureContext.drawImage(image, 0, 0);
    gaitTextures.set(image, textureContext.getImageData(0, 0, 640, 740).data);
  }
  const source = gaitTextures.get(image);
  const pixels = ctx.createImageData(640, 156);
  gait.feet.forEach((foot, leg) => {
    const minX = leg === 0 ? 0 : 307, maxX = leg === 0 ? 307 : 640;
    for (let y = 584; y < 740; y++) {
      const sy = y < 700 - foot.lift ? (y - 584 * foot.lift / 116) / (1 - foot.lift / 116) : y + foot.lift;
      if (sy >= 739) continue;
      const t = Math.max(0, Math.min(1, (sy - 584) / 116));
      const shift = foot.x * t + Math.sin(Math.PI * t) * foot.lift * gait.turn * .3;
      const iy = Math.floor(sy), fy = sy - iy;
      for (let x = Math.max(0, Math.floor(minX + shift)); x < Math.min(640, Math.ceil(maxX + shift)); x++) {
        const sx = x - shift, ix = Math.floor(sx), fx = sx - ix;
        if (ix < minX || ix >= maxX || ix >= 639) continue;
        const dest = ((y - 584) * 640 + x) * 4;
        const origin = (iy * 640 + ix) * 4;
        for (let c = 0; c < 4; c++) {
          pixels.data[dest + c] = (source[origin + c] * (1 - fx) + source[origin + 4 + c] * fx) * (1 - fy) +
            (source[origin + 2560 + c] * (1 - fx) + source[origin + 2564 + c] * fx) * fy;
        }
      }
    }
  });
  ctx.putImageData(pixels, 0, 584);
}

async function startGait(direction) {
  const run = ++gaitRun;
  const image = new Image();
  image.src = await cleanedAvatar(avatarMap.idle[0], "idle");
  try { await image.decode(); } catch { return; }
  if (run !== gaitRun || !idleAvailable()) return;
  const wrap = el("avatarWrap");
  const canvas = el("avatarGait");
  const startOffset = idleOffsetX;
  const started = Date.now();
  const tick = () => {
    if (run !== gaitRun) return;
    const progress = Math.min(1, (Date.now() - started) / 3000);
    const gait = gaitAt(progress, direction);
    const scale = Math.min(el("avatarVisual").clientWidth / 640, el("avatarVisual").clientHeight / 740);
    idleOffsetX = startOffset + gait.root * scale;
    el("avatarStage").style.setProperty("--avatar-offset-x", `${idleOffsetX}px`);
    drawGait(image, gait);
    canvas.hidden = false;
    wrap.dataset.gait = "true";
    if (progress < 1) gaitFrame = requestAnimationFrame(tick);
  };
  tick();
}

function cleanedAvatar(src, pose) {
  const cacheKey = `${src}:${pose}`;
  if (cleanedAvatars.has(cacheKey)) return cleanedAvatars.get(cacheKey);
  const promise = new Promise((resolve) => {
    const image = new Image();
    image.onload = () => {
      try {
        const canvas = document.createElement("canvas");
        canvas.width = image.naturalWidth;
        canvas.height = image.naturalHeight;
        const context = canvas.getContext("2d", { willReadFrequently: true });
        context.drawImage(image, 0, 0);
        const frame = context.getImageData(0, 0, canvas.width, canvas.height);
        const [left, right] = footBounds[pose] || footBounds.wave;
        for (let y = 0; y < canvas.height; y++) {
          for (let x = 0; x < canvas.width; x++) {
            const index = (y * canvas.width + x) * 4;
            const faintEdge = frame.data[index + 3] < 12;
            const outsideFeet = y > canvas.height * .89 && (x < left || x > right);
            const lightFloor = y > canvas.height * .9 && frame.data[index] > 205 && frame.data[index + 1] > 205 && frame.data[index + 2] > 205;
            if (faintEdge || outsideFeet || lightFloor) frame.data[index + 3] = 0;
          }
        }
        context.putImageData(frame, 0, 0);
        resolve(canvas.toDataURL("image/png"));
      } catch {
        resolve(src);
      }
    };
    image.onerror = () => resolve(src);
    image.src = src;
  });
  cleanedAvatars.set(cacheKey, promise);
  return promise;
}

const el = (id) => document.getElementById(id);
const messages = el("messages");
const form = el("chatForm");
const input = el("questionInput");
const avatarFrames = [el("avatarImage"), el("avatarImageNext")];
new ResizeObserver(alignFaceOverlay).observe(el("avatarVisual"));

function randomBetween(minimum, maximum) {
  return minimum + Math.random() * (maximum - minimum);
}

async function showAvatarFrame(src, pose, alt) {
  el("avatarVisual").setAttribute("aria-label", alt);
  const run = ++avatarTransitionRun;
  scheduleBlink();
  const current = avatarFrames[activeAvatarFrame];
  if (current.dataset.source === src) {
    current.classList.add("active");
    current.classList.remove("leaving", "entering");
    avatarFrames[1 - activeAvatarFrame].classList.remove("active", "leaving", "entering");
    el("avatarWrap").dataset.transitioning = "false";
    syncFaceOverlay(current, src);
    return;
  }
  el("avatarWrap").dataset.transitioning = "true";
  const nextIndex = 1 - activeAvatarFrame;
  const next = avatarFrames[nextIndex];
  const cleaned = await cleanedAvatar(src, pose);
  if (run !== avatarTransitionRun) return;
  next.src = cleaned;
  next.dataset.source = src;
  try { await next.decode(); } catch { /* The browser can still display the loaded image. */ }
  if (run !== avatarTransitionRun) return;
  if (!reducedMotion.matches) {
    el("avatarWrap").dataset.transitioning = "true";
    current.classList.add("leaving");
    await new Promise((resolve) => setTimeout(resolve, 90));
  }
  if (run !== avatarTransitionRun) return;
  current.classList.remove("active", "leaving");
  next.classList.add("active", "entering");
  activeAvatarFrame = nextIndex;
  syncFaceOverlay(next, src);
  requestAnimationFrame(() => requestAnimationFrame(() => {
    if (run !== avatarTransitionRun) return;
    next.classList.remove("entering");
    el("avatarWrap").dataset.transitioning = "false";
  }));
}

function cancelIdleMotion() {
  gaitRun++;
  cancelAnimationFrame(gaitFrame);
  el("avatarGait").hidden = true;
  el("avatarWrap").dataset.gait = "false";
  clearTimeout(idleDelayTimer);
  clearTimeout(idleActionTimer);
  const wrap = el("avatarWrap");
  wrap.dataset.idleAction = "none";
}

function idleAvailable() {
  return !reducedMotion.matches && document.visibilityState === "visible" && !state.busy &&
    el("avatarWrap").dataset.talking !== "true" && audioPlayer.paused && !speechRequestController &&
    (!("speechSynthesis" in window) || !window.speechSynthesis.speaking);
}

function chooseIdleAction() {
  const choices = idleActionSpecs.filter((item) => item.name !== lastIdleAction &&
    (item.name !== "sidestep" || !hasWalked));
  const total = choices.reduce((sum, item) => sum + item.weight, 0);
  let pick = Math.random() * total;
  for (const item of choices) {
    pick -= item.weight;
    if (pick <= 0) return item;
  }
  return choices[choices.length - 1];
}

async function runIdleAction() {
  if (!idleAvailable()) return;
  const action = chooseIdleAction();
  const wrap = el("avatarWrap");
  lastIdleAction = action.name;
  wrap.dataset.state = "idle";
  wrap.dataset.boardPoint = "false";
  wrap.dataset.idleAction = action.name;
  if (action.name === "sidestep") {
    const direction = Math.random() < .5 ? -1 : 1;
    hasWalked = true;
    await startGait(direction);
    if (wrap.dataset.idleAction !== "sidestep" || !idleAvailable()) return;
  }
  const [src, alt] = avatarMap[action.pose];
  showAvatarFrame(src, action.pose, alt);
  el("avatarState").textContent = action.label;
  const actionDuration = randomBetween(...action.duration);
  idleActionTimer = setTimeout(() => {
    if (action.name === "sidestep") {
      gaitRun++;
      cancelAnimationFrame(gaitFrame);
      el("avatarGait").hidden = true;
      wrap.dataset.gait = "false";
    }
    wrap.dataset.idleAction = "none";
    if (!idleAvailable()) return;
    const [idleSrc, idleAlt, idleLabel] = avatarMap.idle;
    showAvatarFrame(idleSrc, "idle", idleAlt);
    el("avatarState").textContent = idleLabel;
    scheduleIdle();
  }, actionDuration);
}

function scheduleIdle() {
  clearTimeout(idleDelayTimer);
  if (!idleAvailable()) return;
  idleDelayTimer = setTimeout(runIdleAction, randomBetween(15000, 25000));
}

function bubblePages(text) {
  const clean = String(text).replace(/\s+/g, " ").trim();
  const pages = [];
  let page = "";
  for (const character of Array.from(clean)) {
    page += character;
    if (Array.from(page).length >= 20 || /[。！？!?；;，,]/.test(character)) {
      pages.push(page);
      page = "";
    }
  }
  if (page) pages.push(page);
  return pages;
}

// Anchor to the rendered head, not the transparent PNG/container corner.
// Recalculate during CSS animations too; keep text upright when the pose mirrors.
function followSpeechBubble() {
  if (document.visibilityState !== "visible") return;
  const bubble = el("speechBubble");
  const wrap = el("avatarWrap");
  const stage = el("avatarStage").getBoundingClientRect();
  const origin = wrap.getBoundingClientRect();
  const image = avatarFrames[activeAvatarFrame];
  const rect = image.getBoundingClientRect();
  const key = image.dataset.source?.split("avatar-")[1]?.replace(".png", "");
  const face = faceLandmarks[key] || faceLandmarks.wave;
  const scale = Math.min(rect.width / 640, rect.height / 740);
  const mirrored = wrap.dataset.boardPoint === "true" && wrap.dataset.gait !== "true";
  const cx = mirrored ? 640 - face.mouth[0] : face.mouth[0];
  const headX = rect.left + (rect.width - 640 * scale) / 2 + cx * scale;
  const headY = rect.bottom - 740 * scale + (face.eyes[0][1] - 45) * scale;
  const gap = 108 * scale + 10;
  const rightRoom = stage.right - 10 - (headX + gap);
  const leftRoom = headX - gap - stage.left - 10;
  const side = rightRoom >= Math.min(170, stage.width * .4) || rightRoom >= leftRoom ? "right" : "left";
  const room = side === "right" ? rightRoom : leftRoom;
  bubble.style.width = `${Math.max(60, Math.min(170, room))}px`;
  const width = bubble.offsetWidth;
  let x = side === "right" ? headX + gap : headX - gap - width;
  x = Math.max(stage.left + 8, Math.min(x, stage.right - width - 8));
  const boardBottom = document.querySelector(".blackboard").getBoundingClientRect().bottom + 8;
  const y = Math.max(boardBottom, Math.min(headY, stage.bottom - bubble.offsetHeight - 8));
  bubble.dataset.side = side;
  bubble.style.left = `${x - origin.left}px`;
  bubble.style.top = `${y - origin.top}px`;
}

let bubbleTimer;
function showBubble(text) {
  clearTimeout(bubbleTimer);
  const pages = bubblePages(text);
  let index = 0;
  const next = () => {
    if (document.visibilityState === "hidden") {
      bubbleTimer = setTimeout(next, 500);
      return;
    }
    el("speechBubble").textContent = pages[index] || "";
    const delay = Math.max(2200, Array.from(pages[index] || "").length * 220);
    index += 1;
    if (index < pages.length) bubbleTimer = setTimeout(next, delay);
  };
  next();
}

function setAvatar(name, bubble) {
  const [src, alt, label] = avatarMap[name] || avatarMap.idle;
  const wrap = el("avatarWrap");
  cancelIdleMotion();
  wrap.dataset.state = name;
  wrap.dataset.boardPoint = String(name === "point" && !el("boardCodeShell").hidden);
  showAvatarFrame(src, name, alt);
  el("avatarState").textContent = label;
  if (bubble) showBubble(bubble);
  scheduleIdle();
}

function setTalking(talking) {
  el("avatarWrap").dataset.talking = String(Boolean(talking));
  if (talking) cancelIdleMotion();
}

let blinkTimer;
let blinkEndTimer;
function resetBlink() {
  clearTimeout(blinkEndTimer);
  el("avatarWrap").dataset.blinking = "false";
}
function scheduleBlink() {
  clearTimeout(blinkTimer);
  resetBlink();
  if (reducedMotion.matches || document.visibilityState !== "visible") return;
  blinkTimer = setTimeout(() => {
    const wrap = el("avatarWrap");
    if (!reducedMotion.matches && document.visibilityState === "visible" && wrap.dataset.transitioning !== "true") {
      wrap.dataset.blinking = "true";
      blinkEndTimer = setTimeout(() => { resetBlink(); scheduleBlink(); }, 170);
    } else {
      scheduleBlink();
    }
  }, 3200 + Math.random() * 2800);
}

const languageAliases = {
  "c++": "cpp", cxx: "cpp", cc: "cpp", hpp: "cpp",
  js: "javascript", ts: "typescript", py: "python", sh: "shell", ps1: "powershell",
};

const keywordSets = {
  cpp: new Set("alignas alignof asm auto bool break case catch char class const constexpr continue default delete do double else enum explicit export extern false float for friend goto if inline int long mutable namespace new noexcept nullptr operator private protected public register reinterpret_cast return short signed sizeof static static_assert struct switch template this thread_local throw true try typedef typeid typename union unsigned using virtual void volatile wchar_t while".split(" ")),
  javascript: new Set("async await break case catch class const continue debugger default delete do else export extends false finally for function if import in instanceof let new null of return static super switch this throw true try typeof undefined var void while with yield".split(" ")),
  typescript: new Set("abstract any as async await boolean break case catch class const constructor continue declare default delete do else enum export extends false finally for from function get if implements import in infer instanceof interface is keyof let module namespace never new null number object of private protected public readonly require return set static string super switch symbol this throw true try type typeof undefined unique unknown var void while with yield".split(" ")),
  python: new Set("and as assert async await break class continue def del elif else except False finally for from global if import in is lambda None nonlocal not or pass raise return True try while with yield".split(" ")),
};

const typeWords = new Set("bool char double float int long short signed size_t string unsigned void wchar_t array list map set tuple vector dict str bytes object number boolean".split(" "));

function normalizeLanguage(language = "") {
  const normalized = language.trim().toLowerCase().replace(/^language-/, "");
  return languageAliases[normalized] || normalized || "text";
}

function languageLabel(language) {
  return { cpp: "C++", javascript: "JavaScript", typescript: "TypeScript", python: "Python", shell: "Shell", powershell: "PowerShell", text: "代码" }[language] || language.toUpperCase();
}

function appendHighlightedLine(line, language, target) {
  const pattern = /(\/\/.*|\/\*.*?\*\/|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|#\s*[A-Za-z_][\w]*|\b(?:0x[\da-fA-F]+|\d+(?:\.\d+)?)\b|\b[A-Za-z_]\w*\b|===|!==|==|!=|<=|>=|=>|&&|\|\||<<|>>|\+\+|--|[-+*/%=&|!<>?:~^]+)/g;
  let cursor = 0;
  for (const match of line.matchAll(pattern)) {
    if (match.index > cursor) target.append(document.createTextNode(line.slice(cursor, match.index)));
    const token = match[0];
    const span = document.createElement("span");
    if (token.startsWith("//") || token.startsWith("/*") || (language === "python" && token.startsWith("#"))) span.className = "token-comment";
    else if (token.startsWith("#")) span.className = "token-preprocessor";
    else if (/^["']/.test(token)) span.className = "token-string";
    else if (/^(?:0x[\da-f]+|\d)/i.test(token)) span.className = "token-number";
    else if ((keywordSets[language] || keywordSets.cpp).has(token)) span.className = typeWords.has(token) ? "token-type" : "token-keyword";
    else if (typeWords.has(token)) span.className = "token-type";
    else if (/^[A-Za-z_]\w*$/.test(token) && line.slice(match.index + token.length).trimStart().startsWith("(")) span.className = "token-function";
    else span.className = "token-operator";
    span.textContent = token;
    target.append(span);
    cursor = match.index + token.length;
  }
  if (cursor < line.length) target.append(document.createTextNode(line.slice(cursor)));
}

function renderCodeLines(target, code, language, lineClass) {
  target.replaceChildren();
  code.replace(/\r\n/g, "\n").replace(/\n$/, "").split("\n").forEach((line) => {
    const row = document.createElement("span");
    row.className = lineClass;
    appendHighlightedLine(line, language, row);
    target.append(row);
  });
}

function appendInlineMarkup(target, text) {
  const pattern = /(`[^`\n]+`|\*\*[^*\n]+\*\*)/g;
  let cursor = 0;
  for (const match of text.matchAll(pattern)) {
    if (match.index > cursor) target.append(document.createTextNode(text.slice(cursor, match.index)));
    const value = match[0];
    const node = document.createElement(value.startsWith("`") ? "code" : "strong");
    if (value.startsWith("`")) node.className = "inline-code";
    node.textContent = value.slice(value.startsWith("`") ? 1 : 2, value.startsWith("`") ? -1 : -2);
    target.append(node);
    cursor = match.index + value.length;
  }
  if (cursor < text.length) target.append(document.createTextNode(text.slice(cursor)));
}

function fencedCodeBlocks(text) {
  const blocks = [];
  const pattern = /```([^\r\n`]*)\r?\n([\s\S]*?)```/g;
  for (const match of text.matchAll(pattern)) {
    blocks.push({ language: normalizeLanguage(match[1]), code: match[2] });
  }
  return blocks;
}

function renderMessageContent(target, text) {
  const pattern = /```([^\r\n`]*)\r?\n([\s\S]*?)```/g;
  let cursor = 0;
  for (const match of text.matchAll(pattern)) {
    if (match.index > cursor) {
      const copy = document.createElement("div");
      copy.className = "message-copy";
      appendInlineMarkup(copy, text.slice(cursor, match.index).trim());
      if (copy.textContent) target.append(copy);
    }
    const language = normalizeLanguage(match[1]);
    const block = document.createElement("section");
    block.className = "code-block";
    const heading = document.createElement("div");
    heading.className = "code-heading";
    heading.textContent = languageLabel(language);
    const pre = document.createElement("pre");
    const code = document.createElement("code");
    renderCodeLines(code, match[2], language, "code-line");
    pre.append(code);
    block.append(heading, pre);
    target.append(block);
    cursor = match.index + match[0].length;
  }
  if (cursor < text.length || !target.childNodes.length) {
    const copy = document.createElement("div");
    copy.className = "message-copy";
    appendInlineMarkup(copy, text.slice(cursor).trim());
    target.append(copy);
  }
}

function addMessage(role, text, sources = []) {
  const article = document.createElement("article");
  article.className = `message ${role}`;
  const label = document.createElement("div");
  label.className = "message-label";
  label.textContent = role === "assistant" ? "西西老师" : "我";
  const body = document.createElement("div");
  body.className = "message-body";
  renderMessageContent(body, text);
  article.append(label, body);
  if (sources.length) {
    const sourceButton = document.createElement("button");
    sourceButton.type = "button";
    sourceButton.className = "source-button";
    sourceButton.textContent = `查看 ${sources.length} 条教材依据`;
    sourceButton.addEventListener("click", () => showSources(sources));
    article.append(sourceButton);
  }
  messages.append(article);
  messages.scrollTop = messages.scrollHeight;
  return article;
}

function showSources(sources) {
  const list = el("sourceList");
  list.replaceChildren();
  sources.forEach((source) => {
    const item = document.createElement("section");
    item.className = "source-item";
    const title = document.createElement("b");
    title.textContent = source.section;
    const meta = document.createElement("small");
    meta.textContent = source.filename;
    const excerpt = document.createElement("p");
    excerpt.textContent = source.excerpt;
    item.append(title, meta, excerpt);
    list.append(item);
  });
  el("sourceDialog").showModal();
}

function speechTextFor(text) {
  return text
    .replace(/```[^\n`]*\n?[\s\S]*?```/g, " 代码示例请看黑板。 ")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/!\[[^\]]*\]\([^)]*\)/g, "")
    .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")
    .replace(/(?:\*\*|__)(.+?)(?:\*\*|__)/g, "$1")
    .replace(/^[>#\-+]+\s*/gm, "")
    .replace(/\s+/g, " ")
    .trim();
}

function clearBoardHighlight() {
  if (!state.boardSync) return;
  state.boardSync.activeLine = -1;
  el("boardCode").querySelectorAll(".active").forEach((line) => line.classList.remove("active"));
}

function prepareBoard(answer, spokenText) {
  const blocks = fencedCodeBlocks(answer);
  const shell = el("boardCodeShell");
  if (!blocks.length) {
    shell.hidden = true;
    el("boardText").hidden = false;
    state.boardSync = null;
    return;
  }
  const primary = blocks[0];
  renderCodeLines(el("boardCode"), primary.code, primary.language, "board-code-line");
  el("boardLanguage").textContent = languageLabel(primary.language);
  el("boardText").hidden = true;
  shell.hidden = false;

  const spoken = spokenText || speechTextFor(answer);
  const markerIndex = spoken.indexOf("代码示例请看黑板");
  const markerProgress = markerIndex >= 0 && spoken.length ? markerIndex / spoken.length : 0.2;
  const lines = el("boardCode").querySelectorAll(".board-code-line").length;
  const start = Math.max(0.05, markerProgress - 0.04);
  const end = Math.min(0.94, start + Math.max(0.3, Math.min(0.62, lines * 0.075)));
  state.boardSync = { start, end, lines, activeLine: -1 };
}

function syncBoardToProgress(progress) {
  const sync = state.boardSync;
  if (!sync || !Number.isFinite(progress)) return;
  if (progress < sync.start || progress > sync.end) {
    const wasPointing = el("avatarWrap").dataset.boardPoint === "true";
    clearBoardHighlight();
    if (wasPointing && el("avatarWrap").dataset.talking === "true") {
      setAvatar("speaking");
    }
    return;
  }
  const localProgress = Math.max(0, Math.min(0.999, (progress - sync.start) / (sync.end - sync.start)));
  const index = Math.min(sync.lines - 1, Math.floor(localProgress * sync.lines));
  if (index === sync.activeLine) return;
  clearBoardHighlight();
  sync.activeLine = index;
  const line = el("boardCode").querySelectorAll(".board-code-line")[index];
  if (!line) return;
  line.classList.add("active");
  line.scrollIntoView({ block: "nearest" });
  setAvatar("point", `请看黑板第 ${index + 1} 行代码。`);
}

function stopSound() {
  speechRun += 1;
  if (speechRequestController) speechRequestController.abort();
  speechRequestController = null;
  audioPlayer.pause();
  audioPlayer.onplay = null;
  audioPlayer.ontimeupdate = null;
  audioPlayer.onended = null;
  audioPlayer.onerror = null;
  audioPlayer.removeAttribute("src");
  audioPlayer.load();
  if ("speechSynthesis" in window) window.speechSynthesis.cancel();
  setTalking(false);
  clearBoardHighlight();
}

function updateSoundToggle() {
  el("soundToggle").textContent = state.sound ? "声音开启" : "声音关闭";
  el("soundToggle").setAttribute("aria-pressed", String(state.sound));
}

function addReplayButton(article, payload) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "replay-button";
  button.textContent = "重播声音";
  button.title = "重播这条回答";
  button.addEventListener("click", () => {
    if (!state.sound) {
      state.sound = true;
      localStorage.setItem("xixi-sound", "on");
      updateSoundToggle();
    }
    playAnswer(payload);
  });
  article.append(button);
}

function speechChunks(text) {
  const cleaned = speechTextFor(text);
  if (!cleaned) return [];
  const chunks = [];
  let remaining = cleaned;
  while (remaining.length > 140) {
    const windowText = remaining.slice(0, 140);
    const breakAt = Math.max(
      windowText.lastIndexOf("。"), windowText.lastIndexOf("！"), windowText.lastIndexOf("？"),
      windowText.lastIndexOf("；"), windowText.lastIndexOf("，"), windowText.lastIndexOf(" ")
    );
    const length = breakAt >= 60 ? breakAt + 1 : 140;
    chunks.push(remaining.slice(0, length).trim());
    remaining = remaining.slice(length).trim();
  }
  if (remaining) chunks.push(remaining);
  return chunks;
}

function browserVoice() {
  const voices = window.speechSynthesis.getVoices();
  return voices.find((voice) => voice.lang.toLowerCase().startsWith("zh-cn")) ||
    voices.find((voice) => voice.lang.toLowerCase().startsWith("zh")) || null;
}

function speak(text, payload = {}) {
  if (!state.sound || !("speechSynthesis" in window)) {
    setAvatar("point", "答案已经整理好了，看看右边的讲解吧！");
    return false;
  }
  const spoken = payload.speech_text || speechTextFor(text);
  const chunks = speechChunks(spoken);
  if (!chunks.length) return false;
  prepareBoard(payload.answer || text, spoken);
  const run = ++speechRun;
  const totalLength = chunks.reduce((sum, chunk) => sum + chunk.length, 0);
  let consumedLength = 0;
  window.speechSynthesis.cancel();
  window.speechSynthesis.resume();
  const speakChunk = (index) => {
    if (run !== speechRun) return;
    const utterance = new SpeechSynthesisUtterance(chunks[index]);
    utterance.lang = "zh-CN";
    utterance.rate = 0.94;
    utterance.volume = 1;
    utterance.voice = browserVoice();
    utterance.onstart = () => {
      if (run === speechRun) {
        setTalking(true);
        setAvatar("speaking", chunks[index]);
        syncBoardToProgress(consumedLength / totalLength);
      }
    };
    utterance.onboundary = (event) => {
      if (run === speechRun) syncBoardToProgress((consumedLength + event.charIndex) / totalLength);
    };
    utterance.onend = () => {
      if (run !== speechRun) return;
      consumedLength += chunks[index].length;
      syncBoardToProgress(consumedLength / totalLength);
      if (index + 1 < chunks.length) speakChunk(index + 1);
      else {
        setTalking(false);
        clearBoardHighlight();
        setAvatar("point", "听懂了吗？还可以继续追问我。");
        scheduleIdle();
      }
    };
    utterance.onerror = () => {
      if (run === speechRun) {
        setTalking(false);
        setAvatar("point", "声音播放失败，请点击回答下方的“重播声音”。");
      }
    };
    window.speechSynthesis.speak(utterance);
  };
  speakChunk(0);
  return true;
}

function primeSound() {
  if (!state.sound || !("speechSynthesis" in window)) return;
  window.speechSynthesis.resume();
  window.speechSynthesis.getVoices();
}

async function playAnswer(payload) {
  if (!state.sound) return;
  stopSound();
  const run = speechRun;
  const spoken = payload.speech_text || speechTextFor(payload.answer);
  prepareBoard(payload.answer, spoken);
  if (!payload.audio_url && payload.tts_mode === "system") {
    const controller = new AbortController();
    speechRequestController = controller;
    try {
      const response = await fetch("/api/speech", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: spoken }),
        signal: controller.signal,
      });
      if (!response.ok) throw new Error("本机语音不可用");
      const result = await response.json();
      if (run !== speechRun) return;
      payload.audio_url = result.audio_url;
    } catch {
      if (run !== speechRun) return;
      if (payload.browser_fallback) speak(payload.answer, payload);
      else setAvatar("point", "声音播放失败，请在教师管理中检查语音设置。");
      return;
    } finally {
      if (speechRequestController === controller) speechRequestController = null;
    }
  }
  if (!payload.audio_url) {
    if (payload.browser_fallback || payload.tts_mode === "browser") speak(payload.answer, payload);
    return;
  }

  audioPlayer.src = payload.audio_url;
  audioPlayer.volume = Math.max(0.2, Math.min(Number(payload.volume) || 1, 1));
  audioPlayer.onplay = () => {
    if (run === speechRun) {
      setTalking(true);
      setAvatar("speaking", spoken);
    }
  };
  audioPlayer.ontimeupdate = () => {
    if (run === speechRun && Number.isFinite(audioPlayer.duration) && audioPlayer.duration > 0) {
      syncBoardToProgress(audioPlayer.currentTime / audioPlayer.duration);
    }
  };
  audioPlayer.onended = () => {
    if (run === speechRun) {
      setTalking(false);
      clearBoardHighlight();
      setAvatar(payload.avatar_state || "point", "听懂了吗？还可以继续追问我。");
      scheduleIdle();
    }
  };
  let fellBack = false;
  const fallback = () => {
    if (fellBack || !state.sound || run !== speechRun) return;
    fellBack = true;
    setTalking(false);
    if (payload.browser_fallback) speak(payload.answer, payload);
    else setAvatar("point", "声音播放失败，请点击回答下方的“重播声音”。");
  };
  audioPlayer.onerror = fallback;
  try {
    await audioPlayer.play();
  } catch {
    fallback();
  }
}

async function ask(question) {
  const text = question.trim();
  if (!text || state.busy) return;
  stopSound();
  primeSound();
  state.busy = true;
  el("sendButton").disabled = true;
  input.value = "";
  addMessage("user", text);
  state.history.push({ role: "user", content: text });
  setAvatar("thinking", "我正在教材里查找这个知识点。");
  const loading = addMessage("assistant", "正在查找教材并整理答案…");
  loading.classList.add("loading");

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text, history: state.history.slice(-8) }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "问答服务暂时不可用");
    loading.remove();
    const answerMessage = addMessage("assistant", payload.answer, payload.sources || []);
    if (payload.audio_url || payload.browser_fallback || payload.tts_mode === "system") {
      addReplayButton(answerMessage, payload);
    }
    state.history.push({ role: "assistant", content: payload.answer });
    state.history = state.history.slice(-10);
    el("boardTitle").textContent = (payload.sources && payload.sources[0]?.section) || "知识点讲解";
    el("boardText").textContent = payload.mode === "model" ? "教材依据已理解并整理成新的讲解。" : "当前使用本地规则改述；配置模型后，讲解会更自然。";
    prepareBoard(payload.answer, payload.speech_text);
    setAvatar(payload.avatar_state || "explain", payload.speech_text || speechTextFor(payload.answer));
    if (payload.audio_url || payload.browser_fallback || payload.tts_mode === "browser" || payload.tts_mode === "system") {
      playAnswer(payload);
    } else {
      const pose = fencedCodeBlocks(payload.answer).length ? "point" : (payload.avatar_state || "explain");
      setAvatar(pose);
    }
  } catch (error) {
    loading.remove();
    const message = `暂时没有连接上问答服务。${error.message || "请稍后再试。"}`;
    addMessage("assistant", message);
    setAvatar("idle", "服务开了个小差，请稍后再问我一次。");
  } finally {
    state.busy = false;
    el("sendButton").disabled = false;
    input.focus();
    scheduleIdle();
  }
}

async function loadStatus() {
  try {
    const response = await fetch("/api/status");
    const status = await response.json();
    el("knowledgeCount").textContent = `${status.documents} 份资料`;
    el("systemStatus").className = `status-pill ${status.documents ? "ready" : "warning"}`;
    el("systemStatus").innerHTML = `<i></i>${status.model_configured ? "教材与模型已就绪" : "教材本地改述模式"}`;
    if (status.voice_configured) el("systemStatus").innerHTML = `<i></i>${status.model_configured ? "教材、模型已就绪 · 已配置声音样本" : "教材已就绪 · 已配置声音样本"}`;
  } catch {
    el("systemStatus").className = "status-pill warning";
    el("systemStatus").innerHTML = "<i></i>服务未连接";
  }
}

form.addEventListener("submit", (event) => { event.preventDefault(); ask(input.value); });
input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); ask(input.value); }
});
document.querySelectorAll(".suggestions button").forEach((button) => button.addEventListener("click", () => ask(button.textContent)));
document.querySelectorAll(".lesson").forEach((button) => button.addEventListener("click", () => {
  document.querySelectorAll(".lesson").forEach((item) => item.classList.remove("active"));
  button.classList.add("active");
  ask(button.dataset.question);
}));
el("soundToggle").addEventListener("click", () => {
  state.sound = !state.sound;
  localStorage.setItem("xixi-sound", state.sound ? "on" : "off");
  updateSoundToggle();
  if (state.sound) {
    primeSound();
    speak("声音已开启。");
  } else {
    stopSound();
  }
});
el("clearChat").addEventListener("click", () => {
  stopSound();
  state.history = [];
  messages.replaceChildren();
  addMessage("assistant", "新的一轮开始啦。你想先学哪个 C++ 知识点？");
  el("boardTitle").textContent = "C++ 编程入门";
  el("boardText").textContent = "把问题交给我，我们从教材里一起找答案。";
  prepareBoard("", "");
  setAvatar("wave", "我们重新开始，尽管提问吧！");
});
el("closeSources").addEventListener("click", () => el("sourceDialog").close());
document.addEventListener("visibilitychange", () => {
  cancelIdleMotion();
  scheduleBlink();
  if (document.visibilityState === "visible" && idleAvailable()) {
    setAvatar("idle");
  }
});
reducedMotion.addEventListener("change", () => {
  cancelIdleMotion();
  scheduleBlink();
  if (!reducedMotion.matches && document.visibilityState === "visible") scheduleIdle();
});
updateSoundToggle();
loadStatus();
scheduleBlink();
setAvatar("wave");

let bubbleFollowFrame;
function trackBubble() {
  followSpeechBubble();
  bubbleFollowFrame = requestAnimationFrame(trackBubble);
}
document.addEventListener("visibilitychange", () => {
  cancelAnimationFrame(bubbleFollowFrame);
  if (document.visibilityState === "visible") trackBubble();
});
trackBubble();
