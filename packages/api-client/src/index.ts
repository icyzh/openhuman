export { customInstance } from "./mutator/custom-instance";

export {
  useHealthHealthCheck,
  getHealthHealthCheckQueryKey,
  getHealthHealthCheckQueryOptions,
  healthHealthCheck,
} from "./api/health/health";

export type { HealthHealthCheckQueryResult, HealthHealthCheckQueryError } from "./api/health/health";

export type { HealthResponse } from "./schemas";
