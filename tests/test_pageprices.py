"""Tests for the price cleaner and the per-source event page readers.

Run:  python3 -m unittest discover -s tests
The page texts below are short excerpts of real event pages (as saved by the dump workflow). If a venue
redesigns its site and a reader stops finding the price, the matching test here is the first thing to update.
"""
import os, sys, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(HERE, "..", "parsers"))
import pageprices as pp   # noqa: E402
from _price import clean, from_text   # noqa: E402


class Cleaner(unittest.TestCase):
    def test_formats(self):
        cases = {"0": "Free", "10": "€10", "12,50": "€12,50", "17.00 - 24.00": "€17-24", "12-16€": "€12-16",
                 "0 - 15€": "up to €15", "25+": "from €25", "31.05": "€31,05", "€8.50-€13.50": "€8,50-13,50"}
        for raw, want in cases.items():
            self.assertEqual(clean(raw), want, raw)

    def test_rejects_junk(self):
        for raw in ["", "tba", "€", "$15+", "15 Gulden", "1", "sold out", None, "9999"]:
            self.assertIsNone(clean(raw), raw)

    def test_text_needs_a_price_word(self):
        self.assertEqual(from_text("Bijdrage: €25 inclusief Indiase Chai"), "€25")
        self.assertIsNone(from_text("the ship needs a €100K repair"))


class Readers(unittest.TestCase):
    def check(self, source, text, want):
        self.assertEqual(pp.read(source, text), want)

    def test_iamsterdam(self):
        self.check("iamsterdam", "Tickets\n[Koop tickets vanaf €6,50](https://tickets.muziekgebouw.nl/x)\nGratis toegang](/uit/agenda/other)", "from €6,50")
        self.check("iamsterdam", "Kosten: €15,00 per persoon\nGratis toegang](/uit/agenda/other)", None)   # only the ticket component counts

    def test_mezrab(self):
        self.check("mezrab", "### Tickets\n\nPrice**€ 14,00**\n\nSpaces", "€14")
        self.check("mezrab", "Event starts at 20.00\nEntrance: Donation based\nLanguage: English", "Donation")
        self.check("mezrab", "Entrance is whatever you think a night of connection is worth.", "Donation")
        self.check("mezrab", "Free admission, open to all adventurous musicians", "Free")
        self.check("mezrab", "A night of stories.", None)

    def test_tolhuistuin(self):
        self.check("tolhuistuin", "Doors open at 18:30 Time 19:00 tot 23:59 Language English Entrance Free Location", "Free")
        self.check("tolhuistuin", "Doors open at 19:00 Time 20:30  Entrance With [Paradiso](https://x) Info all our programs are PIN ONLY", None)

    def test_cinetol(self):
        self.check("cinetol", "20:30\n\nTICKET:\n\n€\n\n16.00\n\nDOORSALE:\n\n€\n\n18.00\n", "€16")

    def test_radar(self):
        self.check("radar", "## Price:\n\n* by donation\n\nHet Groene Veld", "Donation")
        self.check("radar", "## Price:\n\n€8 (or Cineville)\n\nNassaukerk", "€8")
        self.check("radar", "## Price:\n\n* free\n\nJoe's Garage", "Free")
        self.check("radar", "Presale/door prices adjusted: our events are volunteers", None)

    def test_amsterdammuseum(self):
        self.check("amsterdammuseum", "**Price**: €12.50\n", "€12,50")
        self.check("amsterdammuseum", "**Price**: Free with a valid entryticket, select this in step 3", None)

    def test_verzetsmuseum(self):
        self.check("verzetsmuseum", "**Prijs:**€10,50 regulier, €5,00 voor Stadspas-houders en €7,50 voor Museumkaart", "€10,50")
        self.check("verzetsmuseum", "De toegang is gratis als je een entreeticket hebt.", None)   # free only with a museum ticket

    def test_verbroederij(self):
        self.check("verbroederij", "**Toegang?** Gratis, gewoon langskomen!", "Free")
        self.check("verbroederij", "**Toegang?** €8 aan de deur", "€8")

    def test_xr(self):
        self.check("xr", "Prijs: Gratis\n", "Free")
        self.check("xr", "Prijs: Vrijwillige bijdrage\nKosten?: Op donatie basis", "Donation")

    def test_iisg(self):
        self.check("iisg", "Entree: Vrije toegang, maar schrijf je in via deze link", "Free")
        self.check("iisg", "Vrije toegang, maar stuur een mail als je erbij wil zijn.", "Free")
        self.check("iisg", "Tijdens onderzoek naar anarchisme stuitten kunstenaars op vrije toegang tot archieven", None)

    def test_marineterrein(self):
        self.check("marineterrein", "Elke maandag 20.00\n\nGratis entree\n\nMeer info", "Free")
        self.check("marineterrein", "tussen de hoofdentree van het Marineterrein en het museum", None)

    def test_offbeat(self):
        self.check("offbeat", "The minimum suggested donation is €10  \n", "Donation, min €10")
        self.check("offbeat", "The suggested donation makes it possible for us to continue", "Donation")

    def test_odessa(self):
        page = ("Bekijk op kaart\n**Anchor of Access**\nOur foundation ticket\n€ 26,80\n**Cultural Contributor**\n"
                "Step up\n€ 29,80\n**Guardian of Odessa**\nincluding the upcoming €100K cost\n€ 34,80\nBoek nu\n€ 26,- online")
        self.check("odessa", page, "from €26,80")

    def test_dezwijger(self):
        self.check("dezwijger", "Grote Zaal\n#### Kies tickets en prijzen Maximaal 10 tickets\nTicket\n€ 11,00\n\n0\nStudentenkaart\n0\n", "€11")
        self.check("dezwijger", "#### Kies tickets en prijzen Maximaal 10 tickets\nVrijkaart\n0\nTotaal\n### Contact", "Free")

    def test_unknown_source_and_empty_text(self):
        self.assertIsNone(pp.read("nosuchsource", "€10"))
        self.assertIsNone(pp.read("mezrab", ""))


class TicketShops(unittest.TestCase):
    def test_paylogic(self):
        t = "Regular\nMembership not required\n\n€ 28.70\nincl. € 3.70 service fee\n"
        self.assertEqual(pp.read_ticket_page("https://tickets.paradiso.nl/abc123", t), "€28,70")
        two = t + "Student\n\n€ 20.00\nincl. € 3.00 service fee\n"
        self.assertEqual(pp.read_ticket_page("https://tickets.paradiso.nl/abc123", two), "from €20")
        self.assertIsNone(pp.read_ticket_page("https://tickets.paradiso.nl/abc123", "interaction_required"))

    def test_weticket_shop(self):
        t = ("#### Tickets\n\nEarly bird\n\n€10.00\n\n+\n\nRegular\n\n€12.50\n\nLate\n\n€15.00\n\n"
             "#### Products\n\n(extra) support donation\n\n€5.00\n")
        self.assertEqual(pp.read_ticket_page("https://desering.weticket.io/x/shop", t), "from €10")
        t2 = "#### Tickets\n\npresale ticket\n\n€15.00 + €0.50\n\ndigital door ticket\n\n€20.00 + €0.50\n"
        self.assertEqual(pp.read_ticket_page("https://garagenoord.weticket.io/x/shop", t2), "from €15,50")
        self.assertIsNone(pp.read_ticket_page("https://a.weticket.io/x/shop", "#### Products\n\nlocker\n\n€2.00\n"))

    def test_links(self):
        t = "[Tickets](https://tickets.paradiso.nl/" + "a" * 32 + "?x=1)"
        self.assertEqual(pp.link_paradiso(t, "u"), "https://tickets.paradiso.nl/" + "a" * 32)
        self.assertEqual(pp.link_weticket("see https://desering.weticket.io/night?lang=en", "https://desering.nl/e"),
                         "https://desering.weticket.io/night/shop")
        self.assertEqual(pp.link_weticket("", "https://skate.weticket.io/jam/"), "https://skate.weticket.io/jam/shop")
        self.assertIsNone(pp.link_weticket("no link", "https://desering.nl/e"))
        listing = ("[Tickets](https://g.weticket.io/one/shop?)\n\n[One](https://www.g.com/club/one)\n\n"
                   "[Tickets](https://g.weticket.io/two/shop)\n\n[Two](https://www.g.com/club/two)")
        self.assertEqual(pp.link_weticket(listing, "https://www.g.com/club/two"), "https://g.weticket.io/two/shop")
        self.assertIsNone(pp.link_weticket(listing, "https://www.g.com/club/three"))   # never borrow another event's shop

    def test_stager(self):
        one = "16/10Fri\nCurbside Lambsear + From 2\nInfo\nTicket\n16.00\nWe use cookies\n"
        self.assertEqual(pp.read_ticket_page("https://cinetol.stager.co/shop/cinetol-tickets/events/1", one), "€16")
        self.assertEqual(pp.link_stager("[TICKETS](https://cinetol.stager.co/shop/cinetol-tickets/events/111683253)", "u"),
                         "https://cinetol.stager.co/shop/cinetol-tickets/events/111683253")

    def test_stager_free_and_concession(self):
        u = "https://cinetol.stager.co/shop/x/events/2"
        self.assertEqual(pp.read_ticket_page(u, "23/10Fri\nPULSO\nInfo\nRSVP [gratis]\n0.00\n"), "Free")
        self.assertEqual(pp.read_ticket_page(u, "22/11Sun\nMengelmoes\nInfo\nEarly bird (seated)\n9.25\nTicket\n11.75\nStadpas houders\n0.00\n"), "from €9,25")

    def test_stager_listing(self):
        shop = ("RADION Amsterdam b.v. Tickets\nMenu\n16/10Fri23:00\nBAILE TRAMA 4TH ANNIVERSARY\nPhase 1\n17.00\nSold out\n"
                "Phase 2\n21.00\nSold out\nPhase 3\n24.00\n17/10Sat23:00\nBomBlastic - The Next Chapter\nPhase 3\n32.00\n"
                "22/10Thu23:00\nLNR: Local Night RADION | ADE edition\nPhase 1\n18.00\nSold out\nPhase 2\n22.00\n"
                "Group tickets (4x)\n67.00\nOnly 11 tickets left!\n23/10Fri23:00\nAURA\nPhase 1\n20.00\nSold out\n")
        u = "https://radionamsterdam.stager.co/shop/default"
        self.assertEqual(pp.read_ticket_page(u, shop, "BAILE TRAMA 4TH ANNIVERSARY", "2026-10-16"), "€24")
        self.assertEqual(pp.read_ticket_page(u, shop, "BomBlastic \u2013 The Next Chapter", "2026-10-17"), "€32")
        self.assertEqual(pp.read_ticket_page(u, shop, "LNR: Local Night RADION | ADE edition", "2026-10-22"), "€22")   # group deal ignored
        self.assertIsNone(pp.read_ticket_page(u, shop, "AURA", "2026-10-23"))              # everything sold out
        self.assertIsNone(pp.read_ticket_page(u, shop, "BomBlastic - The Next Chapter", "2026-10-18"))   # wrong date: never guess

    def test_unknown_platform(self):
        self.assertIsNone(pp.read_ticket_page("https://other.example/x", "€ 10"))


if __name__ == "__main__":
    unittest.main()
