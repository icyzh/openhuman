export { customInstance, ApiError } from "./mutator/custom-instance";

// Health
export {
  useHealthHealthCheck,
  getHealthHealthCheckQueryKey,
  getHealthHealthCheckQueryOptions,
  healthHealthCheck,
} from "./api/health/health";

export type {
  HealthHealthCheckQueryResult,
  HealthHealthCheckQueryError,
} from "./api/health/health";

// Auth
export {
  useAuthMe,
  getAuthMeQueryKey,
  getAuthMeQueryOptions,
  authMe,
} from "./api/auth/auth";

export type {
  AuthMeQueryResult,
  AuthMeQueryError,
} from "./api/auth/auth";

// Employees
export {
  useEmployeesCreateEmployeeRoute,
  useEmployeesListEmployeesRoute,
  useEmployeesGetEmployeeRoute,
  useEmployeesUpdateEmployeeRoute,
  useEmployeesDeleteEmployeeRoute,
  useEmployeesSetDiscordToken,
  useEmployeesSetSlackToken,
  useEmployeesSetStatus,
  getEmployeesCreateEmployeeRouteMutationOptions,
  getEmployeesListEmployeesRouteQueryKey,
  getEmployeesListEmployeesRouteQueryOptions,
  getEmployeesGetEmployeeRouteQueryKey,
  getEmployeesGetEmployeeRouteQueryOptions,
  getEmployeesUpdateEmployeeRouteMutationOptions,
  getEmployeesDeleteEmployeeRouteMutationOptions,
  getEmployeesSetDiscordTokenMutationOptions,
  getEmployeesSetSlackTokenMutationOptions,
  getEmployeesSetStatusMutationOptions,
  getEmployeesPatchSlackSlotRouteMutationOptions,
  employeesCreateEmployeeRoute,
  employeesListEmployeesRoute,
  employeesGetEmployeeRoute,
  employeesUpdateEmployeeRoute,
  employeesDeleteEmployeeRoute,
  employeesSetDiscordToken,
  employeesSetSlackToken,
  employeesSetStatus,
  employeesPatchSlackSlotRoute,
  useEmployeesPatchSlackSlotRoute,
} from "./api/employees/employees";

export type {
  EmployeesCreateEmployeeRouteMutationResult,
  EmployeesCreateEmployeeRouteMutationBody,
  EmployeesCreateEmployeeRouteMutationError,
  EmployeesListEmployeesRouteQueryResult,
  EmployeesListEmployeesRouteQueryError,
  EmployeesGetEmployeeRouteQueryResult,
  EmployeesGetEmployeeRouteQueryError,
  EmployeesUpdateEmployeeRouteMutationResult,
  EmployeesUpdateEmployeeRouteMutationBody,
  EmployeesUpdateEmployeeRouteMutationError,
  EmployeesDeleteEmployeeRouteMutationResult,
  EmployeesDeleteEmployeeRouteMutationError,
  EmployeesSetDiscordTokenMutationResult,
  EmployeesSetDiscordTokenMutationBody,
  EmployeesSetDiscordTokenMutationError,
  EmployeesSetSlackTokenMutationResult,
  EmployeesSetSlackTokenMutationBody,
  EmployeesSetSlackTokenMutationError,
  EmployeesSetStatusMutationResult,
  EmployeesSetStatusMutationBody,
  EmployeesSetStatusMutationError,
  EmployeesPatchSlackSlotRouteMutationResult,
  EmployeesPatchSlackSlotRouteMutationBody,
  EmployeesPatchSlackSlotRouteMutationError,
} from "./api/employees/employees";

// Organizations
export {
  useOrganizationsListOrganizations,
  useOrganizationsCreateOrganization,
  useOrganizationsGetOrganization,
  useOrganizationsUpdateOrganization,
  useOrganizationsDeleteOrganization,
  getOrganizationsListOrganizationsQueryKey,
  getOrganizationsListOrganizationsQueryOptions,
  getOrganizationsCreateOrganizationMutationOptions,
  getOrganizationsGetOrganizationQueryKey,
  getOrganizationsGetOrganizationQueryOptions,
  getOrganizationsUpdateOrganizationMutationOptions,
  getOrganizationsDeleteOrganizationMutationOptions,
  organizationsListOrganizations,
  organizationsCreateOrganization,
  organizationsGetOrganization,
  organizationsUpdateOrganization,
  organizationsDeleteOrganization,
} from "./api/organizations/organizations";

export type {
  OrganizationsListOrganizationsQueryResult,
  OrganizationsListOrganizationsQueryError,
  OrganizationsCreateOrganizationMutationResult,
  OrganizationsCreateOrganizationMutationBody,
  OrganizationsCreateOrganizationMutationError,
  OrganizationsGetOrganizationQueryResult,
  OrganizationsGetOrganizationQueryError,
  OrganizationsUpdateOrganizationMutationResult,
  OrganizationsUpdateOrganizationMutationBody,
  OrganizationsUpdateOrganizationMutationError,
  OrganizationsDeleteOrganizationMutationResult,
  OrganizationsDeleteOrganizationMutationError,
} from "./api/organizations/organizations";

// Documents
export {
  useDocumentsUploadDocument,
  useDocumentsListOrgDocuments,
  useDocumentsGetDocumentRoute,
  useDocumentsDeleteDocumentRoute,
  useDocumentsDownloadDocument,
  useDocumentsGetOrgDocumentsStats,
  getDocumentsUploadDocumentMutationOptions,
  getDocumentsListOrgDocumentsQueryKey,
  getDocumentsListOrgDocumentsQueryOptions,
  getDocumentsGetDocumentRouteQueryKey,
  getDocumentsGetDocumentRouteQueryOptions,
  getDocumentsDeleteDocumentRouteMutationOptions,
  getDocumentsDownloadDocumentQueryKey,
  getDocumentsDownloadDocumentQueryOptions,
  getDocumentsGetOrgDocumentsStatsQueryKey,
  getDocumentsGetOrgDocumentsStatsQueryOptions,
  documentsUploadDocument,
  documentsListOrgDocuments,
  documentsGetDocumentRoute,
  documentsDeleteDocumentRoute,
  documentsDownloadDocument,
  documentsGetOrgDocumentsStats,
} from "./api/documents/documents";

export type {
  DocumentsUploadDocumentMutationResult,
  DocumentsUploadDocumentMutationBody,
  DocumentsUploadDocumentMutationError,
  DocumentsListOrgDocumentsQueryResult,
  DocumentsListOrgDocumentsQueryError,
  DocumentsGetDocumentRouteQueryResult,
  DocumentsGetDocumentRouteQueryError,
  DocumentsDeleteDocumentRouteMutationResult,
  DocumentsDeleteDocumentRouteMutationError,
  DocumentsDownloadDocumentQueryResult,
  DocumentsDownloadDocumentQueryError,
  DocumentsGetOrgDocumentsStatsQueryResult,
  DocumentsGetOrgDocumentsStatsQueryError,
} from "./api/documents/documents";

// Schemas
export type {
  HealthResponse,
  UserResponse,
  HTTPValidationError,
  EmployeeResponse,
  CreateEmployeeRequest,
  UpdateEmployeeRequest,
  StatusRequest,
  DiscordTokenRequest,
  SlackTokenRequest,
  UpdateSlackSlotRequest,
  OrganizationResponse,
  CreateOrganizationRequest,
  UpdateOrganizationRequest,
  BodyDocumentsUploadDocument,
  DocumentResponse,
  DocumentsGetOrgDocumentsStatsParams,
  DocumentsListOrgDocumentsParams,
  DocumentsStatsResponse,
} from "./schemas";
