import "dotenv/config";

import { PrismaPg } from "@prisma/adapter-pg";
import { PrismaClient } from "@prisma/client";

const adapter = new PrismaPg({ connectionString: process.env.DATABASE_URL });
const db = new PrismaClient({ adapter });

async function main() {
  const run = await db.run.create({
    data: {
      appType     : "webapp",
      appName     : "demo_target_app",
      baseUrl     : "http://localhost:3000",
      repoUrl     : "https://github.com/example-org/demo-target-app",
      repoRef     : "main",
      startCommand: "npm start",
      port        : 3000,
      status      : "completed",
      steps: {
        create: [
          {
            stepId         : "signup",
            instruction    : 'Type "alice" into the username field and click "Sign up".',
            dependsOn      : [],
            expectedOutcome: 'Signup status shows "Signed up as alice".',
            status         : "passed",
          },
          {
            stepId         : "create_item",
            instruction    : 'Type "widget" into the item-name field and click "Create item".',
            dependsOn      : ["signup"],
            expectedOutcome: 'Item status shows "Created: widget".',
            status         : "fixed_and_verified",
            prUrl          : "https://github.com/example-org/demo-target-app/pull/1",
            evidence: {
              create: {
                screenshotPath: "evidence/screenshots/create_item_failure.png",
                consoleErrors: [
                  {
                    level: "error",
                    text : "Uncaught (in promise) TypeError: Cannot read properties of undefined (reading 'name')",
                    url  : "http://localhost:3000/app.js",
                  },
                ],
                networkFailures: [
                  {
                    url   : "http://localhost:3000/api/items",
                    status: 500,
                    method: "POST",
                  },
                ],
                modelStatedIntent: "Clicked the Create item button to submit the new item form.",
                confidence: 0.9,
              },
            },
          },
        ],
      },
      logs: {
        create: [
          {
            source   : "test_runner",
            eventType: "tool_call",
            payload  : { tool: "run_ui_test_step", step_id: "signup" },
          },
          {
            source   : "test_runner",
            eventType: "tool_result",
            payload  : { step_id: "signup", status: "passed" },
          },
          {
            source   : "test_runner",
            eventType: "tool_call",
            payload  : { tool: "run_ui_test_step", step_id: "create_item" },
          },
          {
            source   : "test_runner",
            eventType: "tool_result",
            payload  : { step_id: "create_item", status: "failed" },
          },
          {
            source   : "test_runner",
            eventType: "tool_call",
            payload  : { tool: "list_console_messages", step_id: "create_item" },
          },
          {
            source   : "fix_writer",
            eventType: "tool_call",
            payload  : { tool: "dispatch_fix_to_antigravity", step_id: "create_item" },
          },
          {
            source   : "verifier",
            eventType: "tool_result",
            payload  : { step_id: "create_item", status: "resolved" },
          },
          {
            source   : "pr_agent",
            eventType: "tool_result",
            payload  : { pr_url: "https://github.com/example-org/demo-target-app/pull/1" },
          },
        ],
      },
    },
  });

  console.log(`Seeded run ${run.id}`);
}

main()
  .catch((err) => {
    console.error(err);
    process.exit(1);
  })
  .finally(async () => {
    await db.$disconnect();
  });
