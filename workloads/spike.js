import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  scenarios: {
    spike_workload: {
      executor: 'ramping-arrival-rate',
      startRate: 30,
      timeUnit: '1s',
      preAllocatedVUs: 50,
      maxVUs: 250,
      stages: [
        { target: 30, duration: '1m' },
        { target: 220, duration: '30s' }, // Sudden violent spike
        { target: 220, duration: '2m' },  // Peak plateau
        { target: 30, duration: '1m' },   // Rapid cooldown
        { target: 30, duration: '1m' },
      ],
    },
  },
  thresholds: {
    http_req_duration: ['p(95)<350'],
    http_req_failed: ['rate<0.05'],
  },
};

const BASE_URL = __ENV.TARGET_URL || 'http://localhost:8000';

export default function () {
  const res = http.get(`${BASE_URL}/health`);
  check(res, {
    'status is 200': (r) => r.status === 200,
  });
  sleep(0.02);
}
