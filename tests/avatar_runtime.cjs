const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

let now = 0, timerId = 0;
const timers = new Map();
const elements = new Map();
function element(id) {
  if (!elements.has(id)) elements.set(id, {
    dataset: {}, style: { setProperty(name, value) { this[name] = value; } }, children: [],
    classList: { add() {}, remove() {} }, setAttribute() {},
    setPointerCapture() {}, releasePointerCapture() {}, hasPointerCapture: () => true,
    naturalWidth: 640, naturalHeight: 740, clientWidth: 200, clientHeight: 300,
    decode: async () => {},
    getContext: () => ({ clearRect() {}, save() {}, restore() {}, translate() {}, transform() {}, setTransform() {}, drawImage() {} }),
  });
  return elements.get(id);
}
element('faceOverlay').children = Array.from({length: 3}, () => ({style: {}}));
const context = vm.createContext({
  console, Map, Math, Date: { now: () => now },
  localStorage: { getItem: () => 'off' },
  window: { matchMedia: () => ({matches: false}) },
  document: { visibilityState: 'visible', getElementById: element },
  Audio: class { paused = true; }, ResizeObserver: class { observe() {} },
  Image: class { decode = async () => {}; },
  setTimeout(fn, delay) { timers.set(++timerId, {fn, at: now + delay, delay}); return timerId; },
  clearTimeout(id) { timers.delete(id); },
  requestAnimationFrame(fn) {
    if (fn.name !== 'tick') { fn(); return; }
    timers.set(++timerId, {fn, at: now + 10, delay: 10}); return timerId;
  },
  cancelAnimationFrame(id) { timers.delete(id); },
});
const source = fs.readFileSync('app/static/app.js', 'utf8').split('const languageAliases =')[0];
vm.runInContext(source, context);
const run = (code) => vm.runInContext(code, context);
async function settle() { for (let i=0; i<10; i++) await Promise.resolve(); }
async function advance(ms) {
  const end = now + ms;
  while (true) {
    const next = [...timers].filter(([,t]) => t.at <= end).sort((a,b) => a[1].at-b[1].at)[0];
    if (!next) break;
    now = next[1].at; timers.delete(next[0]); next[1].fn(); await settle();
  }
  now = end;
}

(async () => {
  let shift = 0;
  const box = (left, top, width, height) => ({left, top, width, height, right:left+width, bottom:top+height});
  element('avatarStage').getBoundingClientRect = () => box(0, 0, 500, 700);
  element('avatarWrap').getBoundingClientRect = () => box(20+shift, 350, 360, 340);
  for (const id of ['avatarImage', 'avatarImageNext']) {
    element(id).getBoundingClientRect = () => box(35+shift, 350, 280, 324);
  }
  element('speechBubble').offsetWidth = 140;
  element('speechBubble').offsetHeight = 62;
  context.document.querySelector = () => ({getBoundingClientRect: () => box(35, 35, 430, 308)});
  run('followSpeechBubble()');
  const bubbleLeft = parseFloat(element('speechBubble').style.left);
  shift = 40;
  run('followSpeechBubble()');
  assert.equal(parseFloat(element('speechBubble').style.left), bubbleLeft, 'same local anchor means bubble travels exactly with avatar');
  shift = 240;
  run('followSpeechBubble()');
  assert.equal(element('speechBubble').dataset.side, 'left', 'bubble switches sides near right stage edge');
  assert.ok(parseFloat(element('speechBubble').style.top) + 350 >= 351, 'bubble clears board');
  shift = 0;
  const completeText = 'C++是给电脑下命令的语言，能让电脑帮你算数、整理数据和画图。后面的内容也要完整显示。';
  const pages = run(`bubblePages(${JSON.stringify(completeText)})`);
  assert.equal(pages.join(''), completeText, 'paging must preserve every character');
  assert.ok(pages.every(page => Array.from(page).length <= 20));
  run(`showBubble(${JSON.stringify(completeText)})`);
  for (let i = 0; i < pages.length; i++) {
    assert.equal(element('speechBubble').textContent, pages[i]);
    await advance(Math.max(2200, Array.from(pages[i]).length * 220));
  }
  assert.equal(element('speechBubble').textContent, pages.at(-1), 'keep the final page');
  run(`showBubble(${JSON.stringify(completeText)}); showBubble("新的提示。");`);
  await advance(5000);
  assert.equal(element('speechBubble').textContent, '新的提示。', 'cancel obsolete pages');
  run('idleOffsetX = 0; avatarOffsetY = 0; applyAvatarOffset()');
  const clamped = run('clampAvatarOffset(999, -999, {minX: -30, maxX: 160, minY: -220, maxY: 8})');
  assert.deepEqual({x: clamped.x, y: clamped.y}, {x: 160, y: -220}, 'dragging stays inside the stage');
  run('beginAvatarDrag({pointerId: 7, button: 0, clientX: 100, clientY: 500, preventDefault() {}})');
  assert.equal(element('avatarWrap').dataset.dragging, 'true');
  run('moveAvatarDrag({pointerId: 7, clientX: 220, clientY: 400, preventDefault() {}})');
  assert.equal(element('avatarStage').style['--avatar-offset-x'], '120px');
  assert.equal(element('avatarStage').style['--avatar-offset-y'], '-100px');
  assert.equal(element('avatarWrap').style['--avatar-drag-tilt'], '4deg', 'body leans gently toward movement');
  run('endAvatarDrag({pointerId: 7})');
  assert.equal(element('avatarWrap').dataset.dragging, 'false');
  assert.equal(run('dragState'), null);
  assert.equal(run('idleOffsetX'), 120, 'released position stays where the learner placed it');
  assert.equal(run('avatarOffsetY'), -100);
  run('idleOffsetX = 0; avatarOffsetY = 0; applyAvatarOffset()');
  // Mock only rasterization/loading; exercise actual frame and scheduling behavior.
  run('facePatch = () => "data:image/png;base64,test"; cleanedAvatar = async src => src; drawGait = () => {};');
  // Force a walk, then verify it stops at three seconds and never repeats.
  run('Math.random = () => .85; runIdleAction()');
  await settle();
  assert.equal(element('avatarWrap').dataset.idleAction, 'sidestep');
  assert.equal(element('avatarWrap').dataset.gait, 'true');
  assert.equal(run('idleOffsetX'), 0, 'movement must start without teleporting');
  await advance(2999);
  assert.equal(element('avatarWrap').dataset.idleAction, 'sidestep');
  await advance(1);
  assert.equal(element('avatarWrap').dataset.idleAction, 'none');
  assert.equal(element('avatarGait').hidden, true);
  const stoppedOffset = run('idleOffsetX');
  assert.ok(Math.abs(stoppedOffset) > 20);
  assert.equal(element('avatarStage').style['--avatar-offset-x'], `${stoppedOffset}px`, 'bubble and avatar share the gait offset');
  run('cancelIdleMotion()');
  assert.equal(run('idleOffsetX'), stoppedOffset, 'cancellation must keep the standing position');
  for (const direction of [-1, 1]) {
    for (let step = 0; step < 6; step++) {
      const a = run(`gaitAt(${(step + .25) / 6}, ${direction})`);
      const b = run(`gaitAt(${(step + .75) / 6}, ${direction})`);
      const support = 1 - step % 2;
      assert.equal(a.feet[support].lift, 0, 'support foot stays on floor');
      assert.ok(Math.abs(a.root + a.feet[support].x - b.root - b.feet[support].x) < 1e-8, 'support foot must not slide in world space');
      assert.ok(a.feet[step % 2].lift > 0, 'opposite foot lifts');
    }
    const final = run(`gaitAt(1, ${direction})`);
    assert.ok(final.feet.every(foot => Math.abs(foot.x) < 1e-8 && Math.abs(foot.lift) < 1e-8));
    assert.ok(Math.abs(final.turn) < 1e-8);
  }
  run('scheduleIdle()');
  for (let i=0; i<6; i++) {
    const delay = timers.get(run('idleDelayTimer'));
    assert.ok(delay.delay >= 15000 && delay.delay <= 25000);
    await advance(delay.at - now);
    assert.notEqual(element('avatarWrap').dataset.idleAction, 'none');
    assert.notEqual(element('avatarWrap').dataset.idleAction, 'sidestep', 'walking must not repeat');
    const action = timers.get(run('idleActionTimer'));
    await advance(action.at - now);
    assert.equal(element('avatarWrap').dataset.idleAction, 'none');
  }
  run('cancelIdleMotion(); scheduleBlink()');
  const blink = timers.get(run('blinkTimer'));
  assert.ok(blink.delay >= 3200 && blink.delay <= 6000);
  await advance(blink.at-now);
  assert.equal(element('avatarWrap').dataset.blinking, 'true');
  run('setAvatar("wave")'); await settle(); await advance(100);
  assert.equal(element('avatarWrap').dataset.blinking, 'false');
  assert.ok(timers.has(run('blinkTimer')), 'switching during a blink must not stop future blinks');
  run('setTalking(true)');
  assert.equal(element('avatarWrap').dataset.idleAction, 'none');
  assert.equal(timers.has(run('idleDelayTimer')), false);
  assert.equal(timers.has(run('idleActionTimer')), false);
  run('setTalking(false)');
  for (const [pose, expected] of [['idle','idle'],['wave','wave'],['thinking','think'],['explain','explain'],['point','point'],['read','read'],['encourage','wave'],['correct','think'],['speaking','explain']]) {
    run(`setAvatar('${pose}')`); await settle(); await advance(100);
    assert.equal(element('faceOverlay').dataset.pose, expected);
    assert.equal(element('faceOverlay').dataset.ready, 'true');
    assert.equal(element('avatarWrap').dataset.transitioning, 'false');
  }
  run('setAvatar("idle"); setAvatar("wave"); setAvatar("read")');
  await settle(); await advance(200);
  assert.equal(element('faceOverlay').dataset.pose, 'read', 'latest requested frame owns landmarks');
  for (const [width,height] of [[200,300],[300,200],[120,90]]) {
    const image = run('avatarFrames[activeAvatarFrame]');
    image.clientWidth=width; image.clientHeight=height; run('alignFaceOverlay()');
    const style=element('faceOverlay').style, scale=Math.min(width/640,height/740);
    assert.equal(parseFloat(style.width),640*scale);
    assert.equal(parseFloat(style.height),740*scale);
    assert.equal(parseFloat(style.left),(width-640*scale)/2);
    assert.equal(parseFloat(style.top),height-740*scale);
  }
  run('document.visibilityState="hidden"; cancelIdleMotion(); scheduleBlink(); scheduleIdle()');
  assert.equal(timers.has(run('blinkTimer')), false);
  assert.equal(timers.has(run('idleDelayTimer')), false);
  run('document.visibilityState="visible"; reducedMotion.matches=true; scheduleBlink(); scheduleIdle()');
  assert.equal(timers.has(run('blinkTimer')), false);
  assert.equal(timers.has(run('idleDelayTimer')), false);
  console.log('PASS: bounded pointer drag with persistent position, natural lean/settle, single three-second walk, six idle cycles, blinks, cancellation, poses, contain geometry, hidden/reduced motion');
})().catch(error => { console.error(error); process.exitCode=1; });
