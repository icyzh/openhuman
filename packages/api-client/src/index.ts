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
  useAuthRegisterRoute,
  useAuthLogin,
  useAuthMe,
  getAuthMeQueryKey,
  getAuthMeQueryOptions,
  getAuthRegisterRouteMutationOptions,
  getAuthLoginMutationOptions,
  authRegisterRoute,
  authLogin,
  authMe,
} from "./api/auth/auth";

export type {
  AuthRegisterRouteMutationResult,
  AuthRegisterRouteMutationBody,
  AuthRegisterRouteMutationError,
  AuthLoginMutationResult,
  AuthLoginMutationBody,
  AuthLoginMutationError,
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
  employeesCreateEmployeeRoute,
  employeesListEmployeesRoute,
  employeesGetEmployeeRoute,
  employeesUpdateEmployeeRoute,
  employeesDeleteEmployeeRoute,
  employeesSetDiscordToken,
  employeesSetSlackToken,
  employeesSetStatus,
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
  useDocumentsGetStats,
  getDocumentsUploadDocumentMutationOptions,
  getDocumentsListOrgDocumentsQueryKey,
  getDocumentsListOrgDocumentsQueryOptions,
  getDocumentsGetDocumentRouteQueryKey,
  getDocumentsGetDocumentRouteQueryOptions,
  getDocumentsDeleteDocumentRouteMutationOptions,
  getDocumentsDownloadDocumentQueryKey,
  getDocumentsDownloadDocumentQueryOptions,
  getDocumentsGetStatsQueryKey,
  getDocumentsGetStatsQueryOptions,
  documentsUploadDocument,
  documentsListOrgDocuments,
  documentsGetDocumentRoute,
  documentsDeleteDocumentRoute,
  documentsDownloadDocument,
  documentsGetStats,
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
  DocumentsGetStatsQueryResult,
  DocumentsGetStatsQueryError,
} from "./api/documents/documents";

// Schemas
export type {
  HealthResponse,
  LoginRequest,
  RegisterRequest,
  TokenResponse,
  UserResponse,
  HTTPValidationError,
  EmployeeResponse,
  CreateEmployeeRequest,
  UpdateEmployeeRequest,
  StatusRequest,
  DiscordTokenRequest,
  SlackTokenRequest,
  OrganizationResponse,
  CreateOrganizationRequest,
  UpdateOrganizationRequest,
  BodyDocumentsUploadDocument,
  DocumentResponse,
  DocumentsGetStatsParams,
  DocumentsListOrgDocumentsParams,
  DocumentsStatsResponse,
} from "./schemas";
