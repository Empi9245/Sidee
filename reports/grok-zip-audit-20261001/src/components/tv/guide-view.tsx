import { Button } from "@/components/ui/button";
import { copy } from "@/lib/vidaa/i18n";
import { useAppStore } from "@/lib/vidaa/store";

const LINKS = [
  { href: "https://new-vidaa.surge.sh/", label: "new-vidaa.surge.sh" },
  { href: "http://130.49.177.49/", label: "130.49.177.49" },
  { href: "https://web.nuvioapp.space/?wrapper=vidaa", label: "web.nuvioapp.space" },
  { href: "https://app.nuvio.tv/", label: "app.nuvio.tv" },
];

export function GuideView() {
  const lang = useAppStore((s) => s.lang);
  const t = copy[lang];
  const blocks = [
    { title: t.g1t, body: t.g1 },
    { title: t.g2t, body: t.g2 },
    { title: t.g3t, body: t.g3 },
    { title: t.g4t, body: t.g4 },
  ];

  return (
    <div className="grid gap-5">
      <h2 className="font-display text-3xl tracking-tight">{t.guideTitle}</h2>
      {blocks.map((block) => (
        <article
          key={block.title}
          className="rounded-[var(--radius-lg)] bg-surface border border-border p-5 md:p-6"
        >
          <h3 className="font-display text-xl">{block.title}</h3>
          <p className="mt-2 text-muted leading-relaxed">{block.body}</p>
        </article>
      ))}
      <div className="flex flex-wrap gap-3">
        {LINKS.map((link) => (
          <Button
            key={link.href}
            variant="secondary"
            size="md"
            onClick={() => window.location.assign(link.href)}
          >
            {link.label}
          </Button>
        ))}
      </div>
    </div>
  );
}
