import { create } from "zustand";

import type {
  Employee,
  EmployeeDocument,
  HelpContact,
} from "@/data/employees";
import { fetchEmployees } from "@/data/employees";

interface EmployeesState {
  employees: Employee[];
  loaded: boolean;
  load: () => Promise<void>;
  addEmployee: (data: {
    name: string;
    role: string;
    specialization: string;
    department: string;
    model: string;
    duties: string[];
    discordTag: string;
    slackTag: string;
    documents: EmployeeDocument[];
    helpContacts: HelpContact[];
  }) => void;
  updateEmployee: (
    id: string,
    data: Partial<Omit<Employee, "id">>,
  ) => void;
  deleteEmployee: (id: string) => void;
}

let nextId = 100;

export const useEmployeesStore = create<EmployeesState>((set, get) => ({
  employees: [],
  loaded: false,

  load: async () => {
    if (get().loaded) return;
    const employees = await fetchEmployees();
    set({ employees, loaded: true });
  },

  addEmployee: (data) => {
    const employee: Employee = {
      id: `emp-${nextId++}`,
      name: data.name,
      role: data.role,
      specialization: data.specialization,
      department: data.department,
      model: data.model,
      status: "training",
      duties: data.duties,
      discordTag: data.discordTag,
      slackTag: data.slackTag,
      documents: data.documents,
      helpContacts: data.helpContacts,
      deployedAt: new Date().toISOString().slice(0, 10),
    };
    set((state) => ({ employees: [employee, ...state.employees] }));
  },

  updateEmployee: (id, data) => {
    set((state) => ({
      employees: state.employees.map((emp) =>
        emp.id === id ? { ...emp, ...data } : emp,
      ),
    }));
  },

  deleteEmployee: (id) => {
    set((state) => ({
      employees: state.employees.filter((emp) => emp.id !== id),
    }));
  },
}));
