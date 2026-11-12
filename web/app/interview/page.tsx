import Link from "next/link";

export default function InterviewIndexPage() {
  return (
    <div className="max-w-prose space-y-4">
      <h1 className="page-title">Interview prep</h1>
      <p className="text-sm text-muted-foreground">
        Open a job and choose its interview preparation page. Answers are
        grounded in your stored knowledge base and the saved job posting.
      </p>
      <Link className="underline text-sm" href="/jobs">Choose a job →</Link>
    </div>
  );
}
