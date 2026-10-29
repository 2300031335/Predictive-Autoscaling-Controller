import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  scenarios: {
    burst_workload: {
      executor: 'ramping-arrival-rate',
      startRate: 35,
      timeUnit: '1s',
      preAllocatedVUs: 40,
      maxVUs: 200,
      stages: [
        { target: 35, duration: '1m' },
        { target: 150, duration: '15s' }, // Rapid burst
        { target: 150, duration: '1m' },
        { target: 35, duration: '15s' },
        { target: 35, duration: '1m' },
        { target: 150, duration: '15s' }, // Second burst
        { target: 150, duration: '1m' },
        { target: 35, duration: '15s' },
      ],
    },
  },
  thresholds: {
    http_req_duration: ['p(95)<300'],
    http_req_failed: ['rate<0.03'],
  },
};

const BASE_URL = __ENV.TARGET_URL || 'http://localhost:8000';

export default function () {
  const res = http.get(`${BASE_URL}/health`);
  check(res, {
    'status is 200': (r) => r.status === 200,
  });
  sleep(0.05);
}
