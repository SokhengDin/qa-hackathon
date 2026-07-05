"use server";

import { revalidatePath } from "next/cache";

import { db } from "@/lib/db";
import type { ReviewDecisionValue } from "@/lib/types";

export async function submitReviewDecision(
  stepId: string,
  decision: ReviewDecisionValue,
  reviewerNote: string | null,
) {
  await db.reviewDecision.create({
    data: { stepId, decision, reviewerNote },
  });

  revalidatePath("/runs");
}
