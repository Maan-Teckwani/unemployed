import { redirect } from "next/navigation";
import { PageNav } from "@/components/page-nav";
import { ProfileForm } from "@/components/profile-form";
import { SignOutButton } from "@/components/sign-in-button";
import { viewer } from "@/lib/viewer";
import { recentExperiences } from "@/lib/db";
import { ProfileExperiences } from "./profile-experiences";
import { Gender } from "@/lib/gender-options";

export const dynamic = "force-dynamic";

export default async function ProfilePage() {
  const me = await viewer();
  if (!me.signedIn) redirect("/join");
  if (!me.signup) redirect("/join");

  const experiences = await recentExperiences({ signupId: me.signup.id, limit: 100 });

  return (
    <>
      <PageNav signedIn={me.signedIn} />
      <main id="top" className="px-6 pt-28 pb-32 md:px-12 lg:px-24">
        <div className="mx-auto w-full max-w-3xl">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <h1 className="font-serif text-3xl leading-tight sm:text-4xl">Your Profile</h1>
            <SignOutButton />
          </div>

          <div className="mt-8">
            <ProfileForm
              defaultName={me.signup.name}
              initialSeed={me.signup.seed}
              defaultCountry={me.signup.country}
              defaultGender={me.signup.gender as Gender}
              isEdit={true}
            />
          </div>

          <div className="mt-16">
            <h2 className="font-serif text-2xl leading-tight">Your Experiences</h2>
            <ProfileExperiences initialExperiences={experiences} />
          </div>
        </div>
      </main>
    </>
  );
}
