import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  scenarios: {
    periodic_workload: {
      executor: 'ramping-arrival-rate',
      startRate: 50,
      timeUnit: '1s',
      preAllocatedVUs: 40,
      maxVUs: 200,
      stages: [
        { target: 110, duration: '90s' },
        { target: 50, duration: '90s' },
        { target: 110, duration: '90s' },
        { target: 50, duration: '90s' },
      ],
    },
  },
  thresholds: {
    http_req_duration: ['p(95)<250'],
    http_req_failed: ['rate<0.02'],
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
