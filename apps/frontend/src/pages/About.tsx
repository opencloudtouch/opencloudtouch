import { motion } from "framer-motion";
import { useTranslation } from "react-i18next";
import { useState, useEffect } from "react";
import { useHealth } from "../hooks/useHealth";
import { Skeleton } from "../components/LoadingSkeleton";
import "./About.css";

const GITHUB_REPO = "opencloudtouch/opencloudtouch";
const GITHUB_API = `https://api.github.com/repos/${GITHUB_REPO}/releases/latest`;
const BMC_URL = "https://buymeacoffee.com/b49rjg5k6vj";

interface Supporter {
  name: string;
  type: "monthly" | "one-time";
  amount: number;
  monthlyAmount: number;
  firstSupportDate: string;
}

interface UpdateInfo {
  available: boolean;
  latestVersion?: string;
  releaseUrl?: string;
}

// Thank you phrases per language
const THANK_YOU_PHRASES = {
  regular: {
    en: [
      "Thank you for your support! ☕",
      "You make the difference! 🎵",
      "Thanks a lot! 💙",
      "Super cool of you! 🚀",
      "You rock! 🎸",
      "Thanks for being here! 🙌",
      "You're awesome! ⭐",
      "Heartfelt thanks! ❤️",
      "You help us forward! 🌟",
      "Thanks for your support! 💪",
      "You're the hammer! 🔨",
      "Many thanks! 🎉",
      "You're great! 🌈",
      "Thanks for joining! 🤝",
      "You're a hero! 🦸",
      "Thanks for the coffee! ☕",
      "You're fantastic! 👏",
      "Many thanks! 🎁",
      "You make it possible! ✨",
      "Thanks, you legend! 🏆",
    ],
    de: [
      "Danke für deine Unterstützung! ☕",
      "Du machst den Unterschied! 🎵",
      "Vielen Dank! 💙",
      "Mega cool von dir! 🚀",
      "Du rockst! 🎸",
      "Danke, dass du dabei bist! 🙌",
      "Du bist awesome! ⭐",
      "Herzlichen Dank! ❤️",
      "Du hilfst uns weiter! 🌟",
      "Danke für deinen Support! 💪",
      "Du bist der Hammer! 🔨",
      "Vielen lieben Dank! 🎉",
      "Du bist großartig! 🌈",
      "Danke fürs Mitmachen! 🤝",
      "Du bist ein Held! 🦸",
      "Danke für den Kaffee! ☕",
      "Du bist klasse! 👏",
      "Vielen Dank dafür! 🎁",
      "Du machst's möglich! ✨",
      "Danke, du Ehrenmensch! 🏆",
    ],
    es: [
      "¡Gracias por tu apoyo! ☕",
      "¡Marcas la diferencia! 🎵",
      "¡Muchas gracias! 💙",
      "¡Genial de tu parte! 🚀",
      "¡Eres genial! 🎸",
      "¡Gracias por estar aquí! 🙌",
      "¡Eres increíble! ⭐",
      "¡Gracias de corazón! ❤️",
      "¡Nos ayudas a avanzar! 🌟",
      "¡Gracias por tu ayuda! 💪",
      "¡Eres un crack! 🔨",
      "¡Mil gracias! 🎉",
      "¡Eres fantástico! 🌈",
      "¡Gracias por sumarte! 🤝",
      "¡Eres un héroe! 🦸",
      "¡Gracias por el café! ☕",
      "¡Eres espectacular! 👏",
      "¡Muchísimas gracias! 🎁",
      "¡Lo haces posible! ✨",
      "¡Gracias, leyenda! 🏆",
    ],
    fr: [
      "Merci pour ton soutien ! ☕",
      "Tu fais la différence ! 🎵",
      "Un grand merci ! 💙",
      "Trop cool de ta part ! 🚀",
      "Tu assures ! 🎸",
      "Merci d'être là ! 🙌",
      "Tu es formidable ! ⭐",
      "Merci du fond du cœur ! ❤️",
      "Tu nous fais avancer ! 🌟",
      "Merci pour ton aide ! 💪",
      "Tu es au top ! 🔨",
      "Mille mercis ! 🎉",
      "Tu es génial·e ! 🌈",
      "Merci de participer ! 🤝",
      "Tu es un héros ! 🦸",
      "Merci pour le café ! ☕",
      "Tu es fantastique ! 👏",
      "Merci beaucoup ! 🎁",
      "Tu rends ça possible ! ✨",
      "Merci, légende ! 🏆",
    ],
    it: [
      "Grazie per il tuo supporto! ☕",
      "Fai la differenza! 🎵",
      "Mille grazie! 💙",
      "Troppo forte! 🚀",
      "Sei un grande! 🎸",
      "Grazie di essere qui! 🙌",
      "Sei fantastico! ⭐",
      "Grazie di cuore! ❤️",
      "Ci aiuti ad andare avanti! 🌟",
      "Grazie per il tuo aiuto! 💪",
      "Sei un mito! 🔨",
      "Grazie mille! 🎉",
      "Sei eccezionale! 🌈",
      "Grazie per unirti a noi! 🤝",
      "Sei un eroe! 🦸",
      "Grazie per il caffè! ☕",
      "Sei spettacolare! 👏",
      "Tantissime grazie! 🎁",
      "Lo rendi possibile! ✨",
      "Grazie, leggenda! 🏆",
    ],
    ja: [
      "ご支援ありがとうございます！☕",
      "あなたが違いを生み出します！🎵",
      "感謝します！💙",
      "すごくクール！🚀",
      "最高です！🎸",
      "参加してくれてありがとう！🙌",
      "素晴らしい！⭐",
      "心から感謝！❤️",
      "前進の力になります！🌟",
      "サポートに感謝！💪",
      "あなたは最強！🔨",
      "本当にありがとう！🎉",
      "あなたは素敵！🌈",
      "一緒にいてくれて感謝！🤝",
      "あなたはヒーロー！🦸",
      "コーヒーありがとう！☕",
      "ファンタスティック！👏",
      "深く感謝します！🎁",
      "あなたのおかげです！✨",
      "ありがとう、レジェンド！🏆",
    ],
    nl: [
      "Bedankt voor je steun! ☕",
      "Jij maakt het verschil! 🎵",
      "Heel erg bedankt! 💙",
      "Supergaaf van je! 🚀",
      "Je bent geweldig! 🎸",
      "Bedankt dat je erbij bent! 🙌",
      "Je bent awesome! ⭐",
      "Hartelijk dank! ❤️",
      "Je helpt ons verder! 🌟",
      "Bedankt voor je hulp! 💪",
      "Je bent top! 🔨",
      "Duizendmaal dank! 🎉",
      "Je bent fantastisch! 🌈",
      "Bedankt voor het meedoen! 🤝",
      "Je bent een held! 🦸",
      "Bedankt voor de koffie! ☕",
      "Je bent super! 👏",
      "Ontzettend bedankt! 🎁",
      "Jij maakt het mogelijk! ✨",
      "Bedankt, legende! 🏆",
    ],
    pl: [
      "Dziękujemy za wsparcie! ☕",
      "Robisz różnicę! 🎵",
      "Wielkie dzięki! 💙",
      "Super z twojej strony! 🚀",
      "Jesteś świetny! 🎸",
      "Dzięki, że jesteś! 🙌",
      "Jesteś niesamowity! ⭐",
      "Serdeczne dzięki! ❤️",
      "Pomagasz nam iść dalej! 🌟",
      "Dzięki za pomoc! 💪",
      "Jesteś mega! 🔨",
      "Tysiąc dzięki! 🎉",
      "Jesteś wspaniały! 🌈",
      "Dzięki za dołączenie! 🤝",
      "Jesteś bohaterem! 🦸",
      "Dzięki za kawę! ☕",
      "Jesteś fantastyczny! 👏",
      "Bardzo dziękujemy! 🎁",
      "Ty to umożliwiasz! ✨",
      "Dzięki, legendo! 🏆",
    ],
    pt: [
      "Obrigado pelo apoio! ☕",
      "Você faz a diferença! 🎵",
      "Muito obrigado! 💙",
      "Demais da sua parte! 🚀",
      "Você é incrível! 🎸",
      "Obrigado por estar aqui! 🙌",
      "Você é fantástico! ⭐",
      "Obrigado de coração! ❤️",
      "Você nos ajuda a avançar! 🌟",
      "Obrigado pela ajuda! 💪",
      "Você é fera! 🔨",
      "Milhões de agradecimentos! 🎉",
      "Você é maravilhoso! 🌈",
      "Obrigado por participar! 🤝",
      "Você é um herói! 🦸",
      "Obrigado pelo café! ☕",
      "Você é espetacular! 👏",
      "Muitíssimo obrigado! 🎁",
      "Você torna possível! ✨",
      "Obrigado, lenda! 🏆",
    ],
    sv: [
      "Tack för ditt stöd! ☕",
      "Du gör skillnad! 🎵",
      "Tusen tack! 💙",
      "Supercoolt av dig! 🚀",
      "Du rockar! 🎸",
      "Tack för att du finns! 🙌",
      "Du är fantastisk! ⭐",
      "Hjärtligt tack! ❤️",
      "Du hjälper oss framåt! 🌟",
      "Tack för din hjälp! 💪",
      "Du är grym! 🔨",
      "Stort tack! 🎉",
      "Du är underbar! 🌈",
      "Tack för att du är med! 🤝",
      "Du är en hjälte! 🦸",
      "Tack för kaffet! ☕",
      "Du är enastående! 👏",
      "Tusentals tack! 🎁",
      "Du gör det möjligt! ✨",
      "Tack, legend! 🏆",
    ],
  },
  monthly: {
    en: [
      "You're a champion! 🏆💛",
      "Thanks for your loyal support! ✨",
      "You're worth gold! 💰",
      "Wow, thanks for the monthly commitment! 🌟",
      "You're absolutely amazing! 🚀",
      "Thanks for being here every month! 💙",
      "You're a superhero! 🦸‍♂️",
      "Many thanks for your loyalty! 🙏",
      "You make the project possible! 🎉",
      "Thanks for your continuous help! 💪",
      "You're simply fantastic! ⭐",
      "Heartfelt thanks for your loyalty! ❤️",
      "You're priceless! 💎",
      "Thanks for the monthly fuel! ⚡",
      "You're a rockstar! 🎸",
    ],
    de: [
      "Du bist ein Champion! 🏆💛",
      "Danke für deine treue Unterstützung! ✨",
      "Du bist Gold wert! 💰",
      "Wow, danke fürs monatliche Commitment! 🌟",
      "Du bist der absolute Wahnsinn! 🚀",
      "Danke, dass du jeden Monat dabei bist! 💙",
      "Du bist ein Superheld! 🦸‍♂️",
      "Vielen Dank für deine Treue! 🙏",
      "Du machst das Projekt möglich! 🎉",
      "Danke für deine kontinuierliche Hilfe! 💪",
      "Du bist einfach fantastisch! ⭐",
      "Herzlichen Dank für deine Loyalität! ❤️",
      "Du bist unbezahlbar! 💎",
      "Danke fürs monatliche Fuel! ⚡",
      "Du bist ein Rockstar! 🎸",
    ],
    es: [
      "¡Eres un campeón! 🏆💛",
      "¡Gracias por tu apoyo fiel! ✨",
      "¡Vales oro! 💰",
      "¡Gracias por el compromiso mensual! 🌟",
      "¡Eres absolutamente increíble! 🚀",
      "¡Gracias por estar cada mes! 💙",
      "¡Eres un superhéroe! 🦸‍♂️",
      "¡Mil gracias por tu lealtad! 🙏",
      "¡Haces posible el proyecto! 🎉",
      "¡Gracias por tu ayuda continua! 💪",
      "¡Eres simplemente fantástico! ⭐",
      "¡Gracias de corazón por tu fidelidad! ❤️",
      "¡No tienes precio! 💎",
      "¡Gracias por la energía mensual! ⚡",
      "¡Eres una estrella de rock! 🎸",
    ],
    fr: [
      "Tu es un champion ! 🏆💛",
      "Merci pour ton soutien fidèle ! ✨",
      "Tu vaux de l'or ! 💰",
      "Merci pour l'engagement mensuel ! 🌟",
      "Tu es absolument incroyable ! 🚀",
      "Merci d'être là chaque mois ! 💙",
      "Tu es un super-héros ! 🦸‍♂️",
      "Mille mercis pour ta fidélité ! 🙏",
      "Tu rends le projet possible ! 🎉",
      "Merci pour ton aide continue ! 💪",
      "Tu es tout simplement fantastique ! ⭐",
      "Merci du fond du cœur pour ta loyauté ! ❤️",
      "Tu n'as pas de prix ! 💎",
      "Merci pour le carburant mensuel ! ⚡",
      "Tu es une rockstar ! 🎸",
    ],
    it: [
      "Sei un campione! 🏆💛",
      "Grazie per il tuo supporto fedele! ✨",
      "Vali oro! 💰",
      "Grazie per l'impegno mensile! 🌟",
      "Sei assolutamente incredibile! 🚀",
      "Grazie di essere qui ogni mese! 💙",
      "Sei un supereroe! 🦸‍♂️",
      "Mille grazie per la tua fedeltà! 🙏",
      "Rendi possibile il progetto! 🎉",
      "Grazie per il tuo aiuto continuo! 💪",
      "Sei semplicemente fantastico! ⭐",
      "Grazie di cuore per la tua lealtà! ❤️",
      "Sei impagabile! 💎",
      "Grazie per l'energia mensile! ⚡",
      "Sei una rockstar! 🎸",
    ],
    ja: [
      "あなたはチャンピオン！🏆💛",
      "忠実なご支援に感謝！✨",
      "あなたは金の価値！💰",
      "毎月のコミットメントに感謝！🌟",
      "あなたは本当にすごい！🚀",
      "毎月ありがとうございます！💙",
      "あなたはスーパーヒーロー！🦸‍♂️",
      "変わらぬ忠誠に深く感謝！🙏",
      "プロジェクトを可能にしてくれます！🎉",
      "継続的なご支援に感謝！💪",
      "あなたは素晴らしい！⭐",
      "心からの感謝を！❤️",
      "あなたはかけがえのない存在！💎",
      "毎月のエネルギーに感謝！⚡",
      "あなたはロックスター！🎸",
    ],
    nl: [
      "Je bent een kampioen! 🏆💛",
      "Bedankt voor je trouwe steun! ✨",
      "Je bent goud waard! 💰",
      "Wauw, bedankt voor de maandelijkse steun! 🌟",
      "Je bent absoluut geweldig! 🚀",
      "Bedankt dat je er elke maand bent! 💙",
      "Je bent een superheld! 🦸‍♂️",
      "Heel erg bedankt voor je trouw! 🙏",
      "Jij maakt het project mogelijk! 🎉",
      "Bedankt voor je constante hulp! 💪",
      "Je bent gewoonweg fantastisch! ⭐",
      "Hartelijk dank voor je loyaliteit! ❤️",
      "Je bent onbetaalbaar! 💎",
      "Bedankt voor de maandelijkse brandstof! ⚡",
      "Je bent een rockster! 🎸",
    ],
    pl: [
      "Jesteś mistrzem! 🏆💛",
      "Dzięki za wierne wsparcie! ✨",
      "Jesteś na wagę złota! 💰",
      "Dzięki za miesięczne zaangażowanie! 🌟",
      "Jesteś absolutnie niesamowity! 🚀",
      "Dzięki, że jesteś co miesiąc! 💙",
      "Jesteś superbohaterem! 🦸‍♂️",
      "Ogromne dzięki za lojalność! 🙏",
      "Ty umożliwiasz ten projekt! 🎉",
      "Dzięki za ciągłą pomoc! 💪",
      "Jesteś po prostu fantastyczny! ⭐",
      "Serdeczne dzięki za wierność! ❤️",
      "Jesteś bezcenny! 💎",
      "Dzięki za miesięczne paliwo! ⚡",
      "Jesteś gwiazdą rocka! 🎸",
    ],
    pt: [
      "Você é campeão! 🏆💛",
      "Obrigado pelo apoio fiel! ✨",
      "Você vale ouro! 💰",
      "Obrigado pelo compromisso mensal! 🌟",
      "Você é absolutamente incrível! 🚀",
      "Obrigado por estar aqui todo mês! 💙",
      "Você é um super-herói! 🦸‍♂️",
      "Muito obrigado pela lealdade! 🙏",
      "Você torna o projeto possível! 🎉",
      "Obrigado pela ajuda contínua! 💪",
      "Você é simplesmente fantástico! ⭐",
      "Obrigado de coração pela fidelidade! ❤️",
      "Você não tem preço! 💎",
      "Obrigado pelo combustível mensal! ⚡",
      "Você é uma estrela do rock! 🎸",
    ],
    sv: [
      "Du är en mästare! 🏆💛",
      "Tack för ditt trogna stöd! ✨",
      "Du är värd guld! 💰",
      "Tack för det månatliga engagemanget! 🌟",
      "Du är helt fantastisk! 🚀",
      "Tack för att du finns varje månad! 💙",
      "Du är en superhjälte! 🦸‍♂️",
      "Tusen tack för din lojalitet! 🙏",
      "Du gör projektet möjligt! 🎉",
      "Tack för din ständiga hjälp! 💪",
      "Du är helt enkelt fantastisk! ⭐",
      "Hjärtligt tack för din trohet! ❤️",
      "Du är ovärderlig! 💎",
      "Tack för det månatliga bränslet! ⚡",
      "Du är en rockstjärna! 🎸",
    ],
  },
};

/**
 * RFC 4180-compliant CSV line parser.
 * Handles quoted fields (with commas, quotes inside), unquoted fields, and trims whitespace.
 */
function parseCSVLine(line: string): string[] {
  const fields: string[] = [];
  let i = 0;
  const len = line.length;

  while (i <= len) {
    if (i === len) {
      fields.push("");
      break;
    }

    if (line[i] === '"') {
      // Quoted field
      let value = "";
      i++; // skip opening quote
      while (i < len) {
        if (line[i] === '"') {
          if (i + 1 < len && line[i + 1] === '"') {
            // Escaped quote
            value += '"';
            i += 2;
          } else {
            // Closing quote
            i++; // skip closing quote
            break;
          }
        } else {
          value += line[i];
          i++;
        }
      }
      fields.push(value);
      // Skip comma after closing quote
      if (i < len && line[i] === ",") i++;
    } else {
      // Unquoted field
      const commaIdx = line.indexOf(",", i);
      if (commaIdx === -1) {
        fields.push(line.substring(i).trim());
        break;
      } else {
        fields.push(line.substring(i, commaIdx).trim());
        i = commaIdx + 1;
      }
    }
  }

  return fields;
}

export default function About() {
  const { t, i18n } = useTranslation();
  const { data: health, isLoading: healthLoading } = useHealth();

  const [supporters, setSupporters] = useState<Supporter[]>([]);
  const [supportersLoading, setSupportersLoading] = useState(true);
  const [updateInfo, setUpdateInfo] = useState<UpdateInfo>({ available: false });
  const [updateLoading, setUpdateLoading] = useState(true);

  // Get random thank you phrase
  const getRandomThankYou = (isMonthly: boolean) => {
    const currentLang = i18n.language.split("-")[0]; // en-US → en
    const fallbackLang = "en";

    const category = isMonthly ? "monthly" : "regular";
    const phrases =
      THANK_YOU_PHRASES[category][currentLang as keyof typeof THANK_YOU_PHRASES.regular] ||
      THANK_YOU_PHRASES[category][fallbackLang];

    return phrases[Math.floor(Math.random() * phrases.length)];
  };

  // Load supporters from CSV
  useEffect(() => {
    const loadSupporters = async () => {
      try {
        const response = await fetch("/supporters.csv");
        if (!response.ok) {
          setSupporters([]);
          setSupportersLoading(false);
          return;
        }

        let text = await response.text();

        // Strip UTF-8 BOM if present
        if (text.charCodeAt(0) === 0xfeff) {
          text = text.substring(1);
        }

        const lines = text.trim().split("\n").slice(1); // Skip header

        if (lines.length === 0 || lines[0] === "") {
          setSupporters([]);
          setSupportersLoading(false);
          return;
        }

        const parsed: Supporter[] = lines
          .filter((line) => line.trim())
          .map((line) => parseCSVLine(line))
          .filter((fields): fields is string[] => fields.length >= 5)
          .map((fields) => ({
            name: fields[0],
            type: fields[1] as "monthly" | "one-time",
            amount: parseFloat(fields[2]) || 0,
            monthlyAmount: parseFloat(fields[3]) || 0,
            firstSupportDate: fields[4],
          }));

        // Sort by total support: amount + monthlyAmount DESC
        parsed.sort((a, b) => {
          const scoreA = a.amount + a.monthlyAmount;
          const scoreB = b.amount + b.monthlyAmount;
          if (scoreB !== scoreA) return scoreB - scoreA;
          if (a.firstSupportDate !== b.firstSupportDate) {
            return a.firstSupportDate.localeCompare(b.firstSupportDate);
          }
          return a.name.localeCompare(b.name);
        });

        setSupporters(parsed);
        setSupportersLoading(false);
      } catch (error) {
        console.error("Failed to load supporters:", error);
        setSupporters([]);
        setSupportersLoading(false);
      }
    };

    loadSupporters();
  }, []);

  // Check for updates
  useEffect(() => {
    const checkUpdate = async () => {
      if (!health?.version) {
        setUpdateLoading(false);
        return;
      }

      try {
        const response = await fetch(GITHUB_API);
        if (!response.ok) {
          setUpdateLoading(false);
          return;
        }

        const release = await response.json();
        const latestTag = release.tag_name?.replace(/^v/, "");
        const currentVersion = health.version;
        const isNewer = latestTag && latestTag !== currentVersion;

        setUpdateInfo({
          available: isNewer,
          latestVersion: latestTag,
          releaseUrl: release.html_url,
        });
        setUpdateLoading(false);
      } catch (error) {
        console.error("Failed to check for updates:", error);
        setUpdateLoading(false);
      }
    };

    if (health?.version) {
      const timer = setTimeout(checkUpdate, 3000);
      return () => clearTimeout(timer);
    }
  }, [health?.version]);

  // Calculate font size based on support amount
  const getFontSize = (supporter: Supporter, maxAmount: number) => {
    const totalSupport = supporter.amount + supporter.monthlyAmount;
    const ratio = totalSupport / maxAmount;
    const minSize = 12;
    const maxSize = 32;
    return Math.floor(minSize + (maxSize - minSize) * ratio);
  };

  // Generate smooth color gradient
  const generateGradientColor = (index: number, total: number) => {
    const hue = (index / total) * 360;
    const saturation = 60 + (index % 3) * 10;
    const lightness = 55 + (index % 2) * 10;
    return `hsl(${hue}, ${saturation}%, ${lightness}%)`;
  };

  // Clean GitHub URLs
  const cleanName = (name: string) => {
    if (name.startsWith("https://github.com/")) {
      return "@" + name.replace("https://github.com/", "");
    }
    return name;
  };

  const maxAmount = Math.max(...supporters.map((s) => s.amount + s.monthlyAmount), 1);

  return (
    <div className="about-page">
      <motion.div
        className="about-container"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
      >
        {/* Header */}
        <div className="about-header">
          <div className="about-icon">🎵</div>
          <h1 className="about-title">OpenCloudTouch</h1>
          {healthLoading && <Skeleton width="60px" height="24px" borderRadius="20px" />}
          {!healthLoading && health && <span className="about-version">v{health.version}</span>}
        </div>

        {/* Build Info */}
        {!healthLoading && health?.uptime && (
          <p className="about-build-time">
            {t("about.buildTime", {
              time: new Date(Date.now() - health.uptime * 1000).toLocaleString(),
            })}
          </p>
        )}

        {/* Update Check */}
        <div className="about-update-section">
          {updateLoading && (
            <div className="about-update-loading">
              <div className="spinner-small" />
              <span>{t("about.checkingUpdates")}</span>
            </div>
          )}
          {!updateLoading && updateInfo.available && (
            <motion.div
              className="about-update-available"
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
            >
              <div className="update-icon">🆕</div>
              <div className="update-content">
                <p className="update-title">
                  {t("about.updateAvailable", { version: updateInfo.latestVersion })}
                </p>
                <a
                  href={updateInfo.releaseUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn btn-primary btn-sm"
                >
                  {t("about.viewRelease")}
                </a>
              </div>
            </motion.div>
          )}
          {!updateLoading && !updateInfo.available && health && (
            <div className="about-update-current">
              <span className="update-check-icon">✅</span>
              <span>{t("about.upToDate")}</span>
            </div>
          )}
        </div>

        {/* Supporters Wimmelbild */}
        {!supportersLoading && supporters.length > 0 && (
          <motion.div
            className="supporters-wimmelbild-section"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
          >
            <h2 className="supporters-wimmelbild-title">Supp❤️rters</h2>

            <div className="supporters-wimmelbild">
              {supporters.map((supporter, index) => {
                const fontSize = getFontSize(supporter, maxAmount);
                const color = generateGradientColor(index, supporters.length);
                const isMonthly = supporter.monthlyAmount > 0;
                const supporterKey = `${supporter.name}-${index}`;

                return (
                  <motion.span
                    key={supporterKey}
                    className={
                      isMonthly ? "supporter-name-wimmelbild monthly" : "supporter-name-wimmelbild"
                    }
                    style={{
                      fontSize: `${fontSize}px`,
                      color: isMonthly ? undefined : color,
                    }}
                    initial={{ opacity: 0, scale: 0.8 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ delay: index * 0.02 }}
                    title={getRandomThankYou(isMonthly)}
                    onMouseEnter={(e) => {
                      e.currentTarget.title = getRandomThankYou(isMonthly);
                    }}
                  >
                    {cleanName(supporter.name)}
                  </motion.span>
                );
              })}
            </div>
          </motion.div>
        )}

        {/* Links */}
        <div className="about-links-simple">
          <a
            href={`https://github.com/${GITHUB_REPO}`}
            target="_blank"
            rel="noopener noreferrer"
            className="about-link-simple"
          >
            <svg className="icon-github" viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg">
              <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z" />
            </svg>
            GitHub›
          </a>
          <a
            href={`https://github.com/${GITHUB_REPO}/issues/new?template=bug_report.yml`}
            target="_blank"
            rel="noopener noreferrer"
            className="about-link-simple"
          >
            🐛 {t("about.reportBug")}›
          </a>
          <a
            href={BMC_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="about-link-simple about-link-support"
          >
            ☕ {t("about.support")}›
          </a>
        </div>
      </motion.div>
    </div>
  );
}
