"use client";

import { useState, useRef } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowLeftIcon,
  FileTextIcon,
  PlusIcon,
  UploadIcon,
  XIcon,
} from "lucide-react";

import { useEmployeesStore } from "@/stores/employees";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

const EMPLOYEE_TYPES = [
  {
    id: "legal-compliance",
    label: "Legal Compliance Officer",
    description: "Reviews contracts, policies, and regulatory documents",
  },
  {
    id: "support",
    label: "Support Employee",
    description: "Handles customer inquiries and support tickets",
  },
  {
    id: "hr",
    label: "HR Employee",
    description: "Manages onboarding, benefits, and employee questions",
  },
  {
    id: "general",
    label: "General",
    description: "Versatile assistant for any team need",
  },
] as const;

interface HelpContact {
  name: string;
  discordTag: string;
  expertise: string;
}

interface UploadedFile {
  name: string;
  size: number;
}

export default function OnboardPage() {
  const router = useRouter();
  const addEmployee = useEmployeesStore((s) => s.addEmployee);

  const [employeeType, setEmployeeType] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [role, setRole] = useState("");
  const [specialization, setSpecialization] = useState("");
  const [discordTag, setDiscordTag] = useState("");
  const [slackTag, setSlackTag] = useState("");
  const [duties, setDuties] = useState<string[]>([]);
  const [dutyInput, setDutyInput] = useState("");
  const [helpContacts, setHelpContacts] = useState<HelpContact[]>([]);
  const [contactForm, setContactForm] = useState<HelpContact>({
    name: "",
    discordTag: "",
    expertise: "",
  });
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const isValid = name.trim().length > 0;

  const handleAddDuty = () => {
    const trimmed = dutyInput.trim();
    if (!trimmed) return;
    setDuties((prev) => [...prev, trimmed]);
    setDutyInput("");
  };

  const handleRemoveDuty = (index: number) => {
    setDuties((prev) => prev.filter((_, i) => i !== index));
  };

  const handleAddContact = () => {
    if (!contactForm.name.trim() || !contactForm.discordTag.trim()) return;
    setHelpContacts((prev) => [...prev, contactForm]);
    setContactForm({ name: "", discordTag: "", expertise: "" });
  };

  const handleRemoveContact = (index: number) => {
    setHelpContacts((prev) => prev.filter((_, i) => i !== index));
  };

  const handleFilesSelected = (selected: FileList | null) => {
    if (!selected) return;
    setFiles((prev) => [
      ...prev,
      ...Array.from(selected).map((f) => ({ name: f.name, size: f.size })),
    ]);
  };

  const handleRemoveFile = (index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  };

  function formatFileSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  const handleSubmit = () => {
    if (!isValid) return;

    addEmployee({
      name: name.trim(),
      role: role.trim(),
      specialization: specialization.trim(),
      department: "General",
      model: "",
      duties,
      discordTag: discordTag.trim(),
      slackTag: slackTag.trim(),
      documents: files,
      helpContacts,
    });

    router.push("/dashboard");
  };

  return (
    <div className="flex flex-1 flex-col gap-8 px-6 py-6">
      <div className="flex items-center gap-4">
        <Button
          variant="ghost"
          size="sm"
          className="w-fit"
          onClick={() => router.push("/dashboard")}
        >
          <ArrowLeftIcon />
          Back to Team
        </Button>
      </div>

      <div className="mx-auto flex w-full max-w-2xl flex-col gap-10">
        {/* Header */}
        <div className="flex flex-col gap-3">
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">
            Create your AI employee
          </h1>
          <p className="text-base text-muted-foreground">
            Give them a name and role. You can create as many as
            you need.
          </p>
        </div>

        {/* Employee type tiles */}
        <div className="flex flex-col gap-3">
          <Label className="text-base font-medium">Employee type</Label>
          <div className="grid grid-cols-2 gap-3">
            {EMPLOYEE_TYPES.map((type) => {
              const isSelected = employeeType === type.id;
              return (
                <button
                  key={type.id}
                  type="button"
                  onClick={() => {
                    setEmployeeType(type.id);
                    setRole(type.label);
                  }}
                  className={`flex flex-col gap-1.5 rounded-xl border-2 p-4 text-left transition-colors ${
                    isSelected
                      ? "border-primary bg-primary/5"
                      : "border-border hover:border-primary/40 hover:bg-muted/50"
                  }`}
                >
                  <span className="text-base font-medium text-foreground">
                    {type.label}
                  </span>
                  <span className="text-sm text-muted-foreground">
                    {type.description}
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Name */}
        <div className="flex flex-col gap-2">
          <Label htmlFor="name" className="text-base font-medium">
            Name <span className="text-destructive">*</span>
          </Label>
          <p className="text-sm text-muted-foreground">
            What should your team call them? e.g. Allison, Marcus, Alex.
          </p>
          <Input
            id="name"
            placeholder="Allison"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </div>

        {/* Role */}
        <div className="flex flex-col gap-2">
          <Label htmlFor="role" className="text-base font-medium">
            Role
          </Label>
          <p className="text-sm text-muted-foreground">
            What do they do? e.g. Backend Engineer, Product Manager, Support
            Lead.
          </p>
          <Input
            id="role"
            placeholder="Backend Engineer"
            value={role}
            onChange={(e) => setRole(e.target.value)}
          />
        </div>

        {/* Specialization */}
        <div className="flex flex-col gap-2">
          <Label htmlFor="specialization" className="text-base font-medium">
            Specialization
          </Label>
          <p className="text-sm text-muted-foreground">
            What are they especially good at? e.g. Technical billing, SEO content, security audits.
          </p>
          <Input
            id="specialization"
            placeholder="Technical billing & refunds"
            value={specialization}
            onChange={(e) => setSpecialization(e.target.value)}
          />
        </div>

        {/* Discord & Slack */}
        <div className="grid grid-cols-2 gap-3">
          <div className="flex flex-col gap-2">
            <Label htmlFor="discord-tag" className="text-base font-medium">
              Discord
            </Label>
            <Input
              id="discord-tag"
              placeholder="aria_support"
              value={discordTag}
              onChange={(e) => setDiscordTag(e.target.value)}
            />
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="slack-tag" className="text-base font-medium">
              Slack
            </Label>
            <Input
              id="slack-tag"
              placeholder="aria.support"
              value={slackTag}
              onChange={(e) => setSlackTag(e.target.value)}
            />
          </div>
        </div>

        {/* Duties */}
        <div className="flex flex-col gap-3">
          <div className="flex flex-col gap-1">
            <Label className="text-base font-medium">Duties</Label>
            <p className="text-sm text-muted-foreground">
              What are this employee&rsquo;s responsibilities? Add each duty one
              at a time. You can write full paragraphs &mdash; each duty can be
              as detailed as you need.
            </p>
          </div>
          {duties.length > 0 && (
            <div className="flex flex-col gap-2">
              {duties.map((duty, i) => (
                <div
                  key={i}
                  className="flex items-start gap-2 rounded-lg border border-border bg-muted/30 px-3 py-2.5"
                >
                  <span className="min-w-0 flex-1 text-base text-foreground">
                    {duty}
                  </span>
                  <button
                    type="button"
                    onClick={() => handleRemoveDuty(i)}
                    className="mt-0.5 shrink-0 rounded-sm text-muted-foreground hover:text-foreground"
                  >
                    <XIcon className="size-4" />
                  </button>
                </div>
              ))}
            </div>
          )}
          <div className="flex flex-col gap-2">
            <Textarea
              placeholder="e.g. Read all PDFs shared in #legal and review them for compliance risks..."
              value={dutyInput}
              onChange={(e) => setDutyInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                  e.preventDefault();
                  handleAddDuty();
                }
              }}
              rows={3}
            />
            <Button
              type="button"
              variant="outline"
              onClick={handleAddDuty}
              className="shrink-0 w-fit"
            >
              <PlusIcon />
              Add duty
            </Button>
          </div>
        </div>

        {/* Upload reference docs */}
        <div className="flex flex-col gap-3">
          <div className="flex flex-col gap-1">
            <Label className="text-base font-medium">Upload reference docs</Label>
            <p className="text-sm text-muted-foreground">
              PDFs, READMEs, or any files that help your employee understand
              your team&rsquo;s context.
            </p>
          </div>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            className="hidden"
            onChange={(e) => handleFilesSelected(e.target.files)}
            accept=".pdf,.md,.txt,.png,.jpg,.jpeg,.gif,.svg,.webp,.csv,.json,.yml,.yaml"
          />
          <button
            type="button"
            className="flex flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed border-border p-8 transition-colors hover:border-muted-foreground/40 hover:bg-muted/50"
            onClick={() => fileInputRef.current?.click()}
            onDragOver={(e) => {
              e.preventDefault();
              e.currentTarget.classList.add("border-primary", "bg-primary/5");
            }}
            onDragLeave={(e) => {
              e.currentTarget.classList.remove(
                "border-primary",
                "bg-primary/5",
              );
            }}
            onDrop={(e) => {
              e.preventDefault();
              e.currentTarget.classList.remove(
                "border-primary",
                "bg-primary/5",
              );
              handleFilesSelected(e.dataTransfer.files);
            }}
          >
            <UploadIcon className="size-6 text-muted-foreground" />
            <div className="flex flex-col items-center gap-0.5">
              <p className="text-base text-muted-foreground">
                Choose files or drag them here
              </p>
              <p className="text-sm text-muted-foreground/60">
                PDF, Markdown, text, images
              </p>
            </div>
          </button>
          {files.length > 0 && (
            <ul className="flex flex-col gap-1.5">
              {files.map((file, i) => (
                <li
                  key={`${file.name}-${i}`}
                  className="flex items-center gap-2 rounded-lg border border-border bg-muted/30 px-3 py-2"
                >
                  <FileTextIcon className="size-4 shrink-0 text-muted-foreground" />
                  <span className="min-w-0 flex-1 truncate text-sm">
                    {file.name}
                  </span>
                  <span className="shrink-0 text-xs text-muted-foreground">
                    {formatFileSize(file.size)}
                  </span>
                  <button
                    type="button"
                    onClick={() => handleRemoveFile(i)}
                    className="shrink-0 rounded p-0.5 text-muted-foreground transition-colors hover:bg-border hover:text-foreground"
                    aria-label={`Remove ${file.name}`}
                  >
                    <XIcon className="size-3.5" />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Who should the bot ask for help? */}
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-1">
            <Label className="text-base font-medium">
              Who should the bot ask for help?
            </Label>
            <p className="text-sm text-muted-foreground">
              Add people the bot can ping when it&rsquo;s unsure. Include their
              Discord tag and the topics they know about.
            </p>
          </div>

          {helpContacts.length > 0 && (
            <div className="flex flex-col gap-2">
              {helpContacts.map((contact, i) => (
                <div
                  key={i}
                  className="flex items-start gap-2 rounded-lg border border-border bg-muted/30 px-3 py-2.5"
                >
                  <div className="min-w-0 flex-1">
                    <p className="text-base font-medium text-foreground">
                      {contact.name}
                    </p>
                    <p className="text-sm text-muted-foreground">
                      @{contact.discordTag}{" "}
                      {contact.expertise && `· ${contact.expertise}`}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleRemoveContact(i)}
                    className="mt-0.5 shrink-0 rounded-sm text-muted-foreground hover:text-foreground"
                  >
                    <XIcon className="size-4" />
                  </button>
                </div>
              ))}
            </div>
          )}

          <div className="flex flex-col gap-3 rounded-xl border border-border p-4">
            <div className="flex gap-2">
              <div className="flex-1 flex-col gap-1.5">
                <Label htmlFor="contact-name" className="text-sm">
                  Name
                </Label>
                <Input
                  id="contact-name"
                  placeholder="Jane Smith"
                  value={contactForm.name}
                  onChange={(e) =>
                    setContactForm({ ...contactForm, name: e.target.value })
                  }
                />
              </div>
              <div className="flex-1 flex-col gap-1.5">
                <Label htmlFor="contact-discord" className="text-sm">
                  Discord tag
                </Label>
                <Input
                  id="contact-discord"
                  placeholder="vimzh"
                  value={contactForm.discordTag}
                  onChange={(e) =>
                    setContactForm({
                      ...contactForm,
                      discordTag: e.target.value,
                    })
                  }
                />
              </div>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="contact-expertise" className="text-sm">
                Expertise areas
              </Label>
              <Input
                id="contact-expertise"
                placeholder="deployments, finance..."
                value={contactForm.expertise}
                onChange={(e) =>
                  setContactForm({ ...contactForm, expertise: e.target.value })
                }
              />
            </div>
            <Button
              type="button"
              variant="outline"
              onClick={handleAddContact}
              className="w-fit"
            >
              <PlusIcon />
              Add
            </Button>
          </div>
        </div>

        {/* Submit */}
        <div className="flex items-center justify-end gap-3 border-t border-border pt-6">
          <Button
            variant="outline"
            size="lg"
            onClick={() => router.push("/dashboard")}
          >
            Cancel
          </Button>
          <Button size="lg" onClick={handleSubmit} disabled={!isValid}>
            Onboard
          </Button>
        </div>
      </div>
    </div>
  );
}
