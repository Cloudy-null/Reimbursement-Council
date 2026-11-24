# From Submission to Approval: A Zero-Friction Reimbursement Experience

Bupa Arabia Discovery Program, Technology Track. Source: official project brief (docx), copied as text on 2026-11-24.

## 1. Project brief

The Bupa app is a critical touchpoint for millions of members managing their healthcare journey. While digital claims submission has improved accessibility, the current experience still requires members to manually enter information that already exists within uploaded medical documents. This creates friction, increases submission errors, and leads to avoidable claim rejections and processing delays.

At the same time, claims operations teams spend significant effort validating documents, identifying missing information, and manually preparing data for internal claims systems.

Instead of asking members to fill out lengthy forms, the solution uses AI to understand uploaded medical documents, validate claim information before submission, and prepare structured data for automated processing within Bupa's internal systems.

In short: the member uploads their documents, the system does the rest, reading, extracting, validating, flagging gaps, and handing over clean, structured, submission-ready data.

### Problem statement

How might we eliminate manual data entry from the reimbursement claim journey by using AI to read, validate, and structure documents, so that members submit right the first time and claims teams receive processing-ready data?

## 2. Objectives and expected outcomes

- Remove manual data entry from the member reimbursement journey by extracting claim data directly from uploaded medical documents (for example invoices, receipts, medical reports).
- Validate before submission: detect missing documents, unreadable images, incomplete fields, and mismatched details.
- Guide the member clearly on exactly what to fix or add, rather than rejecting the claim after submission.
- Produce structured, machine-readable output aligned to the data model expected by Bupa's internal claims systems, ready for automated or straight-through processing.
- Reduce operational effort for claims teams by minimizing manual document review and re-keying for standard, well-formed claims.

## 3. Background

### Context

Reimbursement claims occur when a member pays out of pocket, typically outside the direct-billing network, and later claims the amount back. The member gathers documents from the provider, uploads them through the app, and manually re-enters details such as service type, description, invoice date, and amounts. Any mismatch between what is typed and what the documents show, or any missing document, can result in a rejection or a request for additional information days later.

On the operations side, each submitted claim is reviewed manually: documents are opened and read, information is cross-checked against what the member entered, gaps are identified, and data is prepared for the internal claims system. This is repetitive, high-volume work that scales linearly with claim volume.

### Materials provided to participants (week 2)

| Material | Description |
|---|---|
| Current process documentation | End-to-end walkthrough of the existing reimbursement claim journey, including operational validation steps and common rejection reasons |
| App walkthrough | A guided walkthrough of the current Bupa app claim submission flow, including screens, fields and validation rules |

### Key considerations

- Document variability: documents arrive as photos, scans and PDFs, in Arabic and English, with inconsistent layouts and variable image quality.
- Data sensitivity: medical documents contain personal health information; privacy, consent and data-handling practices must be considered in the design.
- Integration reality: the output must be consumable by existing internal systems, not just visually presented in the app.
- Accessibility and inclusion: the experience should work for members of varying digital literacy and in both Arabic and English.

## 4. Expected final deliverables

| # | Deliverable | Requirement |
|---|---|---|
| 1 | Solution artifact | A working website that demonstrates the enhancement, built and runnable, not mockups. |
| 2 | Data output | Structured, submission-ready claim data produced by the solution. |
| 3 | Final pitch presentation | 10 to 15 minutes plus 5 minutes Q&A. Covers the problem, solution, live demonstration, impact and feasibility. |
| 4 | Project summary | One to two pages: the problem, the key insight, the solution, the expected impact, and feasibility. |
