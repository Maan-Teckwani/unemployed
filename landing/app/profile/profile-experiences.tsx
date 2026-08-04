"use client";

import { useState } from "react";
import { ExperienceCard } from "@/components/experience-card";
import { ExperienceForm } from "@/components/experience-form";
import { Modal } from "@/components/modal";
import type { ExperienceRow } from "@/lib/db";

export function ProfileExperiences({ initialExperiences }: { initialExperiences: ExperienceRow[] }) {
  const [experiences, setExperiences] = useState(initialExperiences);
  const [editing, setEditing] = useState<ExperienceRow | null>(null);

  async function handleDelete(id: string) {
    if (!confirm("Are you sure you want to delete this experience?")) return;
    try {
      const res = await fetch(`/api/experiences/${id}`, { method: "DELETE" });
      if (res.ok) {
        setExperiences((prev) => prev.filter((e) => e.id !== id));
      } else {
        alert("Failed to delete experience.");
      }
    } catch (error) {
      console.error("Delete failed", error);
      alert("An error occurred while deleting.");
    }
  }

  function handleUpdate(updated: ExperienceRow) {
    setExperiences((prev) => prev.map((e) => (e.id === updated.id ? updated : e)));
    setEditing(null);
  }

  return (
    <div className="mt-8">
      {experiences.length === 0 ? (
        <p className="text-muted-foreground text-sm">
          You have not posted any experiences yet.
        </p>
      ) : (
        <ul className="space-y-4">
          {experiences.map((exp) => (
            <ExperienceCard
              key={exp.id}
              experience={exp}
              onEdit={() => setEditing(exp)}
              onDelete={() => handleDelete(exp.id)}
            />
          ))}
        </ul>
      )}

      <Modal
        open={editing !== null}
        onClose={() => setEditing(null)}
        title="Edit Experience"
      >
        {editing && (
          <ExperienceForm
            initialData={editing}
            onPosted={handleUpdate}
          />
        )}
      </Modal>
    </div>
  );
}
