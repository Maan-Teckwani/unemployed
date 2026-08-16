/**
 * Every user-facing string on this page, in one file.
 *
 * Two reasons it lives here rather than inline in JSX. The em dash check has a
 * single file to walk, and a tone pass is one diff instead of a hunt through
 * components.
 *
 * Rules for anything added here: no em dash, no en dash, no double hyphen
 * standing in for a dash, no ellipsis character. `scripts/check-copy.mjs`
 * enforces that and the build runs it.
 */
export const copy = {
  meta: {
    title: "unemployed",
    // The wordmark alone is the tab title, but it says nothing on its own in a
    // link preview or a search result, so cards get the line underneath it.
    tagline: "unemployed: a free job hunting tool that runs on your laptop",
    description:
      "A free job hunting tool that runs on your own laptop. Finds roles, shows you why they fit, and writes a resume from things you actually did.",
    pages: {
      home: "Job hunting is a full time job. Nobody pays you for it.",
      wall: "The wall",
      wallDescription:
        "Everyone using this to look for work right now. A name, a country and a face each, and nothing else.",
      experiences: "Placement snippets",
      experiencesDescription:
        "What the interview rounds were actually like, written by people who sat them. Filter by company.",
      join: "Join the wall",
      joinDescription:
        "Pick a name and a face, and the setup steps open up. No password, and your email is never shown on the wall.",
    },
  },

  nav: {
    links: [
      { href: "/#what", label: "What it does" },
      // Setup is the section people come back for, and it used to be reachable
      // only by scrolling the whole page or by finishing the join form.
      { href: "/#install", label: "Setup" },
      { href: "/guide", label: "How to use it" },
      { href: "/wall", label: "The wall" },
      { href: "/experiences", label: "Placement snippets" },
    ],
    cta: "Join the wall",
    theme: {
      toDark: "Switch to dark theme",
      toLight: "Switch to light theme",
    },
    menu: {
      open: "Open menu",
      close: "Close menu",
    },
  },

  hero: {
    badge: "Free forever. Runs on your laptop.",
    tagline: "Job hunting is a full time job.",
    taglineEmphasis: "Nobody pays you for it.",
    sub: "So this does the boring half. It finds the roles, scores them against what you have actually done, and writes the resume.",
    primary: "Get started",
    secondary: "See what it does",
    counting: (n: number) =>
      n === 1 ? "1 person on the wall" : `${n} people on the wall`,
    scroll: "Scroll",
  },

  story: {
    label: "Why this exists",
    heading: "I built this because I was the one job hunting.",
    body: [
      "Final year, off campus, and the whole thing was manual. Open twenty career pages, read the same job description written five different ways, guess whether I stood a chance, then rewrite my resume for the fourth time that week.",
      "The part that got me was how little of it was thinking. It was tab management. So I spent my evenings building the thing I wanted to exist, and then I used it to apply to the jobs it found.",
    ],
    kicker: "It is open source because there is no reason it should not be.",
  },

  what: {
    label: "What it does",
    heading: "Six things, done properly.",
    items: [
      {
        title: "Builds your pipeline",
        body: "Reads careers pages straight from ninety plus companies on Greenhouse, Lever, Ashby and SmartRecruiters. Search any company by name to add it, or paste a job description you found somewhere else.",
        detail: "No feed, no promoted posts, no listings that closed in March.",
      },
      {
        title: "Filters on your terms",
        body: "Pick your region and it only keeps jobs you could actually take. Roles asking for more years than you have, senior titles and the wrong function are dropped before you ever see them.",
        detail: "Every exclusion carries the rule that caused it, in plain words.",
      },
      {
        title: "Shows the arithmetic",
        body: "Every role scores out of a hundred from five weighted parts: required skills, meaning, preferred skills, keywords and your stated preferences. No model is asked whether it likes you.",
        detail: "Open any score and read the five numbers that made it.",
      },
      {
        title: "Writes a resume you can defend",
        body: "Every bullet is built from something already in your knowledge base and traced back to it. Anything the model cannot trace, and any number it invents, is thrown away before the page is made.",
        detail: "One page, ATS readable, checked by reading the PDF back out again.",
      },
      {
        title: "Keeps your own template",
        body: "Paste the LaTeX resume you already spent a weekend on and it rewrites the wording section by section, in your layout. A section it cannot rewrite truthfully is left exactly as you wrote it.",
        detail: "Opens straight into Overleaf when you are done.",
      },
      {
        title: "Finds who to talk to",
        body: "Builds targeted searches for the five people worth contacting at a company, alumni first, with a short opening message grounded in what you have actually built. Then it suggests one project to build for that role.",
        detail: "Nothing is scraped. You run the search, so your account is never at risk.",
      },
    ],
  },

  local: {
    label: "Your laptop",
    heading: "Your resume never leaves your machine.",
    body: "No account, nothing to log into, no API key to buy. The model runs locally through Ollama and everything it knows about you is one file on your own disk. The only requests it makes are to public job boards, which is what happens when you open a careers page yourself.",
    points: [
      { title: "Free", body: "There is no server bill, because there is no server." },
      { title: "Private", body: "Your career history is one file that never leaves your laptop." },
      { title: "Yours", body: "Back it up by copying it. Read it, change it, delete it." },
    ],
  },

  install: {
    label: "Getting it running",
    heading: "Four commands, once.",
    locked: "Add yourself to the wall and the setup steps open up.",
    intro:
      "About fifteen minutes, and most of that is a download you can walk away from. No database to install and no Docker. You do not need to have anything set up first: the script installs Python, Node and Ollama itself if they are missing.",
    terminalHint: {
      windows: "Open the Start menu, type PowerShell, and press Enter. Copy each command below into that window and press Enter after each one. Wait for one to finish before starting the next.",
      macos: "Press Command and Space, type Terminal, and press Enter. Copy each command below into that window and press Enter after each one. Wait for one to finish before starting the next.",
      linux: "Open your terminal. Copy each command below into it and press Enter after each one. Wait for one to finish before starting the next.",
    },
    osLabel: "Which computer are you on?",
    // One path per machine, not a menu of options. Every extra choice here was
    // a way to end up with a half working install and no idea which half.
    //
    // Four steps rather than two because the two were wrong: `git clone` leaves
    // you in the folder above the one it made, so the run command could never
    // find the script. The missing `cd` was the first thing everybody hit.
    steps: {
      windows: {
        tab: "Windows",
        list: [
          {
            title: "Install Git, which downloads the code",
            command: "winget install Git.Git -e",
            note: "Safe to run even if you already have Git. It will say so and change nothing. If it asks for permission, say yes.",
          },
          {
            title: "Download the code",
            command: "git clone https://github.com/Maan-Teckwani/unemployed.git",
            note: "This makes a new folder called unemployed wherever you are.",
          },
          {
            title: "Go into the folder you just made",
            command: "cd unemployed",
            note: "Every command after this one has to be run from inside that folder.",
          },
          {
            title: "Start it",
            command: ".\\run.cmd",
            note: "This is the long one. It installs anything missing, downloads the model (about 2 GB, once), sets up the database and opens the app for you.",
          },
        ],
      },
      macos: {
        tab: "Mac",
        list: [
          {
            title: "Install Git, which downloads the code",
            command: "xcode-select --install",
            note: "A window pops up: click Install. If it says the tools are already installed, you are done with this step.",
          },
          {
            title: "Download the code",
            command: "git clone https://github.com/Maan-Teckwani/unemployed.git",
            note: "This makes a new folder called unemployed wherever you are.",
          },
          {
            title: "Go into the folder you just made",
            command: "cd unemployed",
            note: "Every command after this one has to be run from inside that folder.",
          },
          {
            title: "Start it",
            command: "./run.sh",
            note: "This is the long one. It installs anything missing, downloads the model (about 2 GB, once), sets up the database and opens the app for you. Mac may ask for your login password once, so it can install what is missing.",
          },
        ],
      },
      linux: {
        tab: "Linux",
        list: [
          {
            title: "Install Git, which downloads the code",
            command: "sudo apt install git -y",
            note: "Safe to run even if you already have Git. On Fedora or Arch use your own package manager instead.",
          },
          {
            title: "Download the code",
            command: "git clone https://github.com/Maan-Teckwani/unemployed.git",
            note: "This makes a new folder called unemployed wherever you are.",
          },
          {
            title: "Go into the folder you just made",
            command: "cd unemployed",
            note: "Every command after this one has to be run from inside that folder.",
          },
          {
            title: "Start it",
            command: "./run.sh",
            note: "This is the long one. On Linux the script names anything missing rather than installing it, so install what it asks for and run it again.",
          },
        ],
      },
    },
    outroBefore: "It opens",
    outroAfter: "for you when it is ready. The first run takes about fifteen minutes. You can walk away during it.",
    port: "http://localhost:3000",
    portLabel: "localhost:3000",
    // The most common question the page never answered.
    againHeading: "Starting it again another day",
    againBody:
      "You only do the four steps above once. After that, open a terminal and run these two:",
    againNote:
      "It skips everything it has already done and goes straight to opening the app.",
    guideBefore: "First time? Read",
    guideLink: "how to actually use this",
    guideAfter: "before you start. Fifteen minutes of setup decides how good everything after it is.",
  },

  // The teaser on the home page. The real thing lives at /guide.
  guideTeaser: {
    label: "Before you start",
    heading: "The setup decides everything after it.",
    body: "This is not a search engine you type into. It reads what you have actually done and matches it against real postings, which means the half hour you spend feeding it is the half hour that decides whether the output is any good.",
    cta: "Read the guide",
    points: [
      {
        title: "Write it all down first",
        body: "Every project, internship, hackathon, certification. In detail, with numbers.",
      },
      {
        title: "Set your region before anything else",
        body: "It decides which jobs are even stored, not just which ones are shown.",
      },
      {
        title: "Then it is ten minutes a day",
        body: "Open the shortlist, generate, send. The long part happens once.",
      },
    ],
  },

  /**
   * The questions people actually ask, answered in the same voice as the rest of
   * the page: plainly, including the parts that are not flattering.
   *
   * Rendered as native details elements, so every answer is in the page whether
   * or not it has been opened. That is what makes them worth having here rather
   * than in a modal: a search engine reads them, and so does anyone who lands on
   * the page with scripting off.
   */
  faq: {
    label: "Questions",
    heading: "The things people ask before they install it.",
    items: [
      {
        q: "Is it actually free, or free until it is not?",
        a: "Free, and there is nothing to charge for. It runs on your laptop, so there is no server to pay for and no usage to meter. There is no account, no plan, and no card. The code is public and you can read exactly what it does.",
      },
      {
        q: "Where does my resume go?",
        a: "Nowhere. Your career history is one file on your own disk, and the model that reads it runs on your machine through Ollama. The only requests the app makes are to public job boards, which is the same thing that happens when you open a careers page yourself.",
      },
      {
        q: "Do I need to know how to code?",
        a: "You need to be willing to copy four commands into a terminal once. The page walks you through opening one. After that it is an ordinary website in your browser. If that first part sounds like too much, this is honestly not ready for you yet.",
      },
      {
        q: "What does it need to run?",
        a: "A laptop with a few GB free. The setup script installs Python, Node and Ollama itself if they are missing, then downloads a model that is about 2 GB, once. There is no database to install and no Docker.",
      },
      {
        q: "How long does the first run take?",
        a: "About fifteen minutes, and nearly all of it is a download you can walk away from. Starting it again on another day takes two commands and a few seconds.",
      },
      {
        q: "Does it apply to jobs for me?",
        a: "No, and that is deliberate. It finds the roles, scores them, and writes the resume. You read it, you decide, and you press send on the company's own page. Nothing is submitted anywhere on your behalf.",
      },
      {
        q: "Will it invent things to make me look better?",
        a: "It is built so that it cannot. Every bullet has to cite the accomplishment it came from, and any number in a bullet has to already appear in that accomplishment. A line that fails either check is dropped rather than shipped.",
      },
      {
        q: "Which countries does it cover?",
        a: "It reads public job boards, so coverage follows the companies that use them. You set your region first, and that decides which roles are stored at all. India, the US, the UK, Europe, Canada, Australia and Singapore each have their own list, and there is an option for no location filter.",
      },
      {
        q: "Can it use my own resume template?",
        a: "Yes. If you keep your resume in Overleaf, you can hand it your LaTeX and it rewrites your own document rather than handing you someone else's layout. There is also a plain PDF built for machine readers if you do not have a template you care about.",
      },
      {
        q: "Do I need to be on the wall to use it?",
        a: "No. The wall is a headcount of people doing the same thing, and joining it opens the setup steps on this page. The tool itself does not know or care whether you joined.",
      },
    ],
  },

  guide: {
    label: "How to use it",
    heading: "Half an hour once, ten minutes a day.",
    intro:
      "Nothing here is hard. The only way to get a bad result is to rush the knowledge base, so this spends most of its time on that.",

    firstRun: {
      label: "The first half hour",
      heading: "Setting it up, once.",
      steps: [
        {
          title: "Do the homework before you open the app",
          time: "20 minutes, offline",
          body: "Open a blank document and write down everything you have done. Every project, every internship, every hackathon, every certification, every position of responsibility. For each one: what the problem was, what you built, which tools you used, and what changed because of it. Numbers wherever you have them, even rough ones. Users, latency, marks, team size, hours saved.",
          why: "This is the single thing that decides output quality. The app never invents a fact, by design, so a resume can only be as specific as what you gave it. Three vague lines produce three vague bullets. A page of real detail produces bullets you can defend in an interview.",
        },
        {
          title: "Fill in your profile",
          time: "1 minute",
          body: "Name, email, education and your college. The college is not decoration: alumni are the highest answering group in outreach, and this is the field that finds them.",
        },
        {
          title: "Import the document",
          time: "5 minutes, mostly waiting",
          body: "Upload your resume and that document on the Import page. Your own model reads them and proposes accomplishment chunks, one per thing you did. Read them. Fix the wording. Delete anything wrong. Nothing is saved until you press save.",
          why: "Reviewing here is cheaper than finding a wrong bullet on a resume you already sent.",
        },
        {
          title: "Set your filters",
          time: "2 minutes",
          body: "Region first, because it decides which jobs are even stored. Then role families, the most years of experience a posting may ask for, and the cities you would actually move to. Preferred cities are a nudge in ranking, not a wall, because a great role in the wrong city is still worth seeing.",
        },
        {
          title: "Fetch jobs",
          time: "10 minutes, walk away",
          body: "One button. It reads every company you track, drops what does not fit, and scores the rest against your knowledge base in the same run. Go and do something else while it works.",
        },
      ],
    },

    daily: {
      label: "After that",
      heading: "The ten minute loop.",
      steps: [
        {
          title: "Open the shortlist",
          body: "The home page tells you how many roles are worth applying to today. Start there, not with the full list.",
        },
        {
          title: "Read why it scored",
          body: "Open a role and the five numbers behind its score are on the page, with the skills you match and the ones you do not. If the reasoning looks wrong, your knowledge base is missing something. Go and add it.",
        },
        {
          title: "Generate the resume",
          body: "One click per role. Read it, edit any wording that sounds unlike you, download it. It is deleted from the app ten minutes later, so download it before you close the tab.",
        },
        {
          title: "Do the outreach",
          body: "Every role comes with searches for five kinds of people and a short opening message. Open the alumni one first. Send three. It takes four minutes and it is the highest return part of the whole process.",
        },
        {
          title: "Mark it applied",
          body: "So tomorrow's shortlist is the roles you have not touched yet.",
        },
      ],
    },

    weekly: {
      label: "Every week or so",
      heading: "Keeping it sharp.",
      steps: [
        {
          title: "Add what you built this week",
          body: "Finished a project, shipped a feature, cleared a certification? Put it in the knowledge base the same day. Every future resume gets it for free.",
        },
        {
          title: "Add companies you care about",
          body: "Search any company by name in filters. If it has a public board, one click starts tracking it.",
        },
        {
          title: "Fetch again",
          body: "New postings, expired ones marked, everything rescored against a knowledge base that now knows more about you.",
        },
      ],
    },

    mistakes: {
      label: "Do not do this",
      heading: "The four ways to get a bad result.",
      items: [
        {
          title: "Uploading only your resume",
          body: "A resume is already compressed to one page. Feed it the long, ugly, detailed version of your career and let the app do the compressing, differently for every role.",
        },
        {
          title: "Skipping the review step",
          body: "The model proposes, you approve. Thirty seconds of reading here is what makes every later bullet trustworthy.",
        },
        {
          title: "Leaving the region unset",
          body: "It is a hard filter, not a preference. Set it wrong and you will be reading jobs you cannot take.",
        },
        {
          title: "Judging it before you have fed it",
          body: "An empty knowledge base scores everything badly and writes nothing worth sending. That is not the app being wrong, it is the app refusing to make things up.",
        },
      ],
    },

    closing: {
      heading: "That is the whole thing.",
      body: "Set it up properly once, spend ten minutes a day, and put back into the knowledge base whatever you build. It gets better at the job the longer you use it, because it knows more about you and nothing about anyone else.",
    },
  },

  auth: {
    signIn: "Continue with Google",
    signOut: "Sign out",
    signInHeading: "Sign in to join the wall.",
    signInBody:
      "One tap with Google. No password to make up, and nothing to log into later.",
    profileHeading: "Now pick a name and a face.",
    profileBody:
      "This is what everyone else sees. Your real name and your Google picture are not stored and never appear on the wall.",
    nameFromGoogle: "Taken from your Google account. Change it to whatever you want shown.",
    whyGoogle: "Google tells two people apart, and gives us an address to reach you on. Your email is kept, is never shown on the wall, and is never given to anyone else. Nothing is posted on your behalf.",
    notYou: "Wrong account?",
    signedInAs: (name: string) => `Signed in as ${name}`,

    // What the roughly one in twenty sees when the sign in does not complete.
    // The default page for this says "there is a problem with the server
    // configuration", which is both frightening and, in almost every real case,
    // wrong: the server is fine and a cookie went missing. These say the true
    // thing and give them the one action that fixes it.
    errorHeading: "That did not go through.",
    errorBody:
      "Google sent you back, but the browser dropped the cookie that proves the sign in started here. Nothing is wrong with your account, and nothing was saved.",
    errorRetry: "Try again",
    errorInApp:
      "If you opened this from inside another app, Instagram or LinkedIn for instance, open it in your normal browser first. Those built in browsers often block the cookie this needs.",
    errorStale:
      "It can also happen if the tab sat for a while before you finished, or if you came back here with the back button. Starting again fixes both.",
    errorDeniedHeading: "You did not finish at Google.",
    errorDeniedBody:
      "The sign in was cancelled on Google's screen, so nothing happened here. You can start again whenever you want.",
  },

  join: {
    label: "The wall",
    heading: "Put yourself on the wall.",
    body: "A name, where you are, and a face. That is all anyone else sees. Your email is kept so we can reach you about the tool, and there is nothing to log into later.",
    why: "It is here so the next person landing on this page can see they are not the only one doing this.",
    nameLabel: "What should we call you",
    namePlaceholder: "first name + last name",
    countryLabel: "Where are you",
    genderLabel: "Avatar",
    genderOptions: {
      female: "Female",
      male: "Male",
      neutral: "Rather not say",
    },
    faceLabel: "Pick a face",
    faceHint: "Any of these. You can change it later from your profile.",
    faceOption: (n: number) => `Face ${n}`,
    moreFaces: "Show more faces",
    submit: "Join the wall",
    submitting: "Adding you",
    saved: "Profile updated.",
    joined: "You are on the wall",
    joinedBody: "Look up, you are in the crowd behind the headline. The setup steps are open now.",
    errors: {
      empty: "Needs a name, any name.",
      tooLong: "Twenty four characters or fewer.",
      profane: "Pick something else.",
      country: "Pick a country.",
      mustSignIn: "Your sign in expired. Sign in again and retry.",
      rateLimited: "That is a few too many. Try again in ten minutes.",
      generic: "That did not go through. Try again in a moment.",
    },
  },

  wall: {
    heading: "Who else is here",
    empty: "Nobody yet. You can be first.",
    caption: (n: number) =>
      n === 1 ? "1 person is running this" : `${n} people are running this`,
    offline: "Cannot reach the wall right now.",
    tapHint: "Pick anyone to read their placement snippets.",
    dragHint: "Drag the wall to move around it. More people load as you go.",
    you: "You",
    youAria: "You, pinned to the front of the wall",
    loadingMore: "Loading more people.",
    personAria: (name: string) => `Placement snippets from ${name}`,
    personLoading: "Looking that up.",
    personEmpty: (name: string) => `${name} has not posted a snippet yet.`,
    personCount: (n: number) =>
      n === 1 ? "1 placement snippet" : `${n} placement snippets`,
  },

  experiences: {
    label: "Placement snippets",
    heading: "What actually got asked.",
    body: "Short reports from people on the wall. Company, role, and a round by round account of how it went, including the ones that ended in a no.",
    filterLabel: "Filter by company",
    filterPlaceholder: "Type a company name",
    empty: "Nobody has posted one yet. You can be first.",
    noMatches: (company: string) => `Nobody has posted about ${company} yet.`,
    postCta: "Share a snippet",
    locked: "Join the wall to share or read the full detail.",
    resultLabels: {
      offer: "Offer",
      rejected: "Rejected",
      withdrawn: "Withdrew",
      pending: "In progress",
    },
    roundTypeLabels: {
      oa: "Online assessment",
      technical: "Technical",
      system_design: "System design",
      hr: "HR",
      managerial: "Managerial",
      group_discussion: "Group discussion",
      other: "Other",
    },
    outcomeLabels: {
      cleared: "Cleared",
      rejected: "Rejected",
      pending: "Pending",
    },
    flag: "Report",
    flagged: "Reported",
    hideRounds: "Hide rounds",
    roundCount: (n: number) => (n === 1 ? "1 round" : `${n} rounds`),
    form: {
      companyLabel: "Company",
      companyPlaceholder: "e.g. Freshworks",
      roleLabel: "Role",
      rolePlaceholder: "e.g. SDE 1",
      resultLabel: "Result",
      summaryLabel: "Summary",
      summaryPlaceholder: "How the process went overall",
      roundsLabel: "Rounds",
      roundTypeLabel: "Type",
      roundDescriptionLabel: "What happened",
      roundOutcomeLabel: "Outcome",
      addRound: "Add another round",
      removeRound: "Remove",
      submit: "Post",
      submitting: "Posting",
      posted: "Posted. Thanks for sharing.",
      errors: {
        empty: "This field can't be empty.",
        tooLong: "That's too long.",
        profane: "Pick different words.",
        rounds: "Fill in every round properly.",
        mustSignIn: "Your sign in expired. Sign in again and retry.",
        mustJoinWall: "Join the wall first, then come back to post.",
        rateLimited: "That's a few too many. Try again later.",
        generic: "That did not go through. Try again in a moment.",
      },
    },
  },

  footer: {
    built: "Built by a student who was job hunting and got tired of doing it by hand.",
    repo: "Source on GitHub",
    licence: "MIT licensed",
    avatars: "Avatars by DiceBear, Open Peeps, CC0",
  },
} as const;
