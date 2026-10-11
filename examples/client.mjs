// Node 22+; no dependencies. Any language can implement this HTTP contract.
const base = process.env.RL_SIM_URL || 'http://127.0.0.1:8000';
const request = async (method, path, body) => {
  const response = await fetch(`${base}/api/v1${path}`, {
    method, headers: { 'Content-Type': 'application/json' },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  if (!response.ok) throw new Error(`${response.status}: ${await response.text()}`);
  return response.json();
};
const world = await request('POST', '/worlds', { template: 'driving' });
console.log('World:', world.id, 'Actions:', world.description.action_names);
try {
  await request('POST', `/worlds/${world.id}/reset`, { seed: 42 });
  for (let i = 0; i < 100; i++) {
    const state = await request('POST', `/worlds/${world.id}/step`, { action: [0.25, 0] });
    if (i % 20 === 0) console.log({ time: state.time, reward: state.reward, ...state.info });
    if (state.terminated || state.truncated) break;
  }
} finally {
  await request('DELETE', `/worlds/${world.id}`);
}
