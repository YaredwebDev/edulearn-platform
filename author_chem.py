"""Author high-quality Approved assessment items for flagship subject content.
Grounded strictly in the Grade 11 Chemistry Unit 1 study notes already in the DB."""
import json, db
db.init_db()

# chemistry grade 11 unit 1 lesson id mapping
subj = db.query("SELECT id FROM subjects WHERE grade=11 AND code='chem'")[0]['id']
unit1 = db.query("SELECT id,number,title FROM units WHERE subject_id=? AND number=1", (subj,))[0]
lessons = {r['number']: r['id'] for r in db.query("SELECT id,number FROM lessons WHERE unit_id=? ORDER BY number", (unit1['id'],))}

def mcq(lid, concept, prompt, choices, correct, why, diff="Medium"):
    db.execute("""INSERT INTO questions(scope,lesson_id,subject_id,qtype,prompt,choices,answer,answer_index,
                  explanation,difficulty,concept,status,sort,created_at) VALUES('lesson',?,?,?,?,?,?,?,?,?,?,?,0,?)""",
               (lid, subj, "mcq", prompt, json.dumps(choices), choices[correct], correct, why, diff, concept, "Approved", db.now()))
def tf(lid, concept, prompt, is_true, why, diff="Easy"):
    db.execute("""INSERT INTO questions(scope,lesson_id,subject_id,qtype,prompt,choices,answer,answer_index,
                  explanation,difficulty,concept,status,sort,created_at) VALUES('lesson',?,?,?,?,?,?,?,?,?,?,?,0,?)""",
               (lid, subj, "tf", prompt, json.dumps(["True","False"]), "True" if is_true else "False",
                0 if is_true else 1, why, diff, concept, "Approved", db.now()))
def flash(lid, front, back):
    db.execute("INSERT INTO flashcards(lesson_id,front,back,sort) VALUES(?,?,?,0)", (lid, front, back))

L1 = lessons[1]   # 1.1 historical development / atomic nature of matter
L2 = lessons[2]   # 1.2 Dalton & modern
L3 = lessons[3]   # 1.3 early experiments (electron, nucleus)
L4 = lessons[4]   # 1.4 nucleus make-up, isotopes
L5 = lessons[5]   # 1.5 EMR & spectra & Bohr & de Broglie
L6 = lessons[6]   # 1.6 quantum mechanical model
L7 = lessons[7]   # 1.7 electron configurations
L8 = lessons[8]   # 1.8 configs & periodic table / periodic properties
L9 = lessons[9]   # key terms
L10= lessons[10]  # key equations

# ---------------- Lesson 1.1 ----------------
mcq(L1,"Atomic theory history","The idea that matter is composed of tiny indivisible particles was first proposed in ancient Greece by:",
    ["Democritus","Dalton","Thomson","Rutherford"],0,"Democritus proposed that matter consists of indivisible particles which he called 'atomos' (atoms).","Easy")
mcq(L1,"Atomic theory history","Which scientist proposed the law of conservation of mass?",
    ["Proust","Lavoisier","Dalton","Thomson"],1,"Lavoisier is credited with the law of conservation of mass, a foundation for the atomic theory.")
mcq(L1,"Atomic theory history","The law of definite proportions is also known as the law of:",
    ["Multiple proportions","Conservation of mass","Constant composition","Gay-Lussac"],2,"The law of definite proportions states a compound always contains the same elements in the same proportion by mass.")
tf(L1,"Atomic theory history","The atomic theory developed gradually, building on the earlier ideas of the Greeks and on the laws of chemical combination.",True,"The historical development combined Greek atomism with the laws of conservation of mass and definite proportions.")
mcq(L1,"Laws of matter","Which of these is a statement of the law of multiple proportions?",
    ["Two elements can form more than one compound","A compound has fixed composition","Mass is conserved in a reaction","Atoms are indivisible"],0,"The law of multiple proportions describes two elements forming more than one compound in different mass ratios.")
flash(L1,"Atomos","The Greek word for 'indivisible'; Democritus proposed matter is made of indivisible particles.")
flash(L1,"Law of conservation of mass","Mass is neither created nor destroyed in a chemical reaction (Lavoisier).")
flash(L1,"Law of definite proportions","A compound always contains the same elements in the same proportion by mass.")
flash(L1,"Law of multiple proportions","When two elements form more than one compound, the masses of one combining with a fixed mass of the other are in a simple whole-number ratio.")

# ---------------- Lesson 1.2 Dalton & Modern ----------------
mcq(L2,"Dalton's theory","According to Dalton's atomic theory, atoms of the same element are:",
    ["Different in mass","Identical","Divisible","Transmutable"],1,"Dalton held that atoms of a given element are identical (and that atoms are indivisible).","Easy")
tf(L2,"Modern atomic theory","The modern atomic theory corrects Dalton by stating that atoms are divisible into subatomic particles.",True,"Modern theory says atoms are made of protons, neutrons and electrons, so they are divisible.")
mcq(L2,"Modern atomic theory","Which idea is a correction of Dalton's theory by the modern atomic theory?",
    ["Atoms are indivisible","Atoms of an element are identical","Isotopes of an element exist","Atoms combine in whole-number ratios"],2,"Modern theory recognises isotopes, so not all atoms of an element are identical.")
mcq(L2,"Limitations","Dalton's theory could NOT explain:",
    ["Combining ratios","The existence of isotopes","Conservation of mass","Fixed composition"],1,"Dalton assumed identical atoms; the existence of isotopes is a limitation the modern theory fixes.")
flash(L2,"Dalton's postulates","Matter made of indivisible atoms; atoms of an element identical; atoms combine in whole-number ratios; atoms neither created nor destroyed.")
flash(L2,"Modern atomic theory","Corrects Dalton: atoms are divisible; isotopes exist; atoms can transform in nuclear reactions.")

# ---------------- Lesson 1.3 Early experiments ----------------
mcq(L3,"Cathode rays","Cathode rays were discovered to be streams of negatively charged particles called:",
    ["Protons","Neutrons","Electrons","Alpha particles"],2,"Thomson showed cathode rays bend toward the positive plate, so they are negatively charged electrons (1897).","Easy")
tf(L3,"Discovery of electron","J.J. Thomson measured the charge-to-mass ratio of the electron but could not measure its charge and mass separately.",True,"Thomson found the electron's charge-to-mass ratio; Millikan later measured the electron's charge using the oil-drop experiment.")
mcq(L3,"Discovery of electron","Robert Millikan measured the charge on the electron using the:",
    ["Cathode-ray tube","Oil-drop experiment","Gold-foil experiment","Mass spectrometer"],1,"Millikan's oil-drop experiment gave e = -1.602e-19 C.")
mcq(L3,"Radioactivity","Alpha (α) particles emitted during radioactivity are identical to:",
    ["Electrons","Helium nuclei","Neutrons","Protons"],1,"An alpha particle carries a charge twice the magnitude of the electron and mass ~4x a hydrogen atom, i.e. a helium nucleus.")
mcq(L3,"Radioactivity","Beta (β) particles are:",
    ["Helium nuclei","Electrons emitted from the nucleus","Neutrons","Photons"],1,"Beta particles are electrons that come from inside the nucleus.")
mcq(L3,"Radioactivity","The neutron was discovered by:",
    ["Rutherford","Chadwick","Bohr","Thomson"],1,"James Chadwick discovered the neutron.")
flash(L3,"Cathode rays","Beams of electrons emitted from the cathode in an evacuated tube; bend toward the positive plate.")
flash(L3,"Oil-drop experiment","Millikan's method that measured the electron's charge, e = -1.602e-19 C.")
flash(L3,"Alpha particle","Helium nucleus emitted in radioactive decay (positive, ~4x H mass).")
flash(L3,"Beta particle","An electron emitted from the nucleus during radioactive decay.")

# ---------------- Lesson 1.4 Nucleus & isotopes ----------------
mcq(L4,"Subatomic particles","Which subatomic particle has negligible mass?",
    ["Proton","Neutron","Electron","Alpha"],2,"The electron has a very small mass compared with the proton and neutron.")
mcq(L4,"Subatomic particles","The atomic number (Z) of an atom equals its number of:",
    ["Neutrons","Protons","Nucleons","Electrons in all shells"],1,"The atomic number is the number of protons in the nucleus.")
tf(L4,"Mass number","The mass number A equals the number of protons plus the number of neutrons.",True,"A = Z + N.")
mcq(L4,"Isotopes","Isotopes are atoms of the same element that have the same number of protons but different numbers of:",
    ["Electrons","Neutrons","Protons","Nuclei"],1,"Isotopes differ in neutron number, so they differ in mass number.")
mcq(L4,"Isotopes","Chlorine-35 and chlorine-37 are:",
    ["Isotopes","Isobars","Isotones","Molecules"],0,"They have the same atomic number but different mass numbers (same protons, different neutrons).")
flash(L4,"Atomic number (Z)","Number of protons in the nucleus; defines the element.")
flash(L4,"Mass number (A)","Total number of protons + neutrons in the nucleus.")
flash(L4,"Isotopes","Atoms of the same element with the same number of protons but different numbers of neutrons.")
flash(L4,"Nucleons","The collective name for protons and neutrons in the nucleus.")

# ---------------- Lesson 1.5 EMR, Bohr, de Broglie ----------------
mcq(L5,"EMR","Which is the correct ordering of electromagnetic radiation by increasing energy of a photon?",
    ["X-rays, visible, radio","Radio, visible, X-rays","Visible, radio, X-rays","Gamma, visible, radio"],1,"Photon energy increases with frequency; radio has the lowest and X-rays/gamma the highest energy.")
mcq(L5,"Quantum","A photon is a:",
    ["Particle of light carrying energy E = hν","Continuous wave","Nucleus particle","Neutral particle"],0,"A photon is a quantum of electromagnetic radiation with energy proportional to frequency (E = hν).")
mcq(L5,"Bohr model","In the Bohr model, the energy of an electron in a hydrogen atom is quantised, meaning the electron:",
    ["Can have any energy","Occupies only certain allowed orbits","Loses all energy gradually","Spirals into the nucleus"],1,"Bohr proposed electrons occupy only certain allowed (quantised) orbits around the nucleus.")
tf(L5,"Spectra","Each element has a unique line (emission) spectrum, which can be used to identify the element.",True,"Line spectra are characteristic fingerprints of elements.")
mcq(L5,"de Broglie","de Broglie proposed that matter particles like electrons have:",
    ["Only particle nature","Only wave nature","Wave-particle duality (a wavelength)","No wavelength"],2,"de Broglie suggested particles have an associated wavelength, giving wave-particle duality.")
mcq(L5,"Wave-particle duality","The wave-particle duality of matter (electrons) was proposed by:",
    ["Bohr","Planck","de Broglie","Rutherford"],2,"de Broglie (1924) proposed matter waves for electrons.")
flash(L5,"Electromagnetic radiation","Energy propagated as electric and magnetic waves; characterised by wavelength and frequency.")
flash(L5,"Photon","Quantum of light; energy E = hν where h is Planck's constant.")
flash(L5,"Bohr model","Model where electrons orbit the nucleus only in certain allowed (quantised) energy levels.")
flash(L5,"de Broglie wavelength","Wavelength associated with a moving particle, λ = h/(mv); basis of wave-particle duality.")

# ---------------- Lesson 1.6 Quantum mechanical model ----------------
mcq(L6,"Quantum numbers","Which set of quantum numbers describes the principal energy level?",
    ["n","l","ml","ms"],0,"The principal quantum number n specifies the main energy level/shell.")
mcq(L6,"Quantum numbers","The magnetic quantum number ml describes the:",
    ["Energy level","Subshell type","Orientation of the orbital in space","Electron spin"],2,"ml specifies the spatial orientation of an orbital within a subshell.")
tf(L6,"Quantum numbers","The spin quantum number ms can have only two values, +1/2 and -1/2.",True,"Electrons in the same orbital have opposite spins described by ms = +1/2 or -1/2.")
mcq(L6,"Quantum mechanical model","In the quantum mechanical model, an atomic orbital is best described as a:",
    ["Fixed circular path","Region of high probability of finding an electron","Orbit shell around nucleus","Point particle trajectory"],1,"An orbital is a region of space where the probability of finding an electron is high.")
mcq(L6,"Subshells","The azimuthal (angular momentum) quantum number l = 2 corresponds to which subshell?",
    ["s","p","d","f"],2,"l = 0(s), 1(p), 2(d), 3(f).")
flash(L6,"Orbital","Region in an atom where there is a high probability of finding an electron.")
flash(L6,"Principal quantum number n","Main energy level of an electron.")
flash(L6,"Pauli exclusion principle","No two electrons in an atom can have the same set of all four quantum numbers.")
flash(L6,"Subshell letters","l = 0 → s, 1 → p, 2 → d, 3 → f.")

# ---------------- Lesson 1.7 Electronic configurations ----------------
mcq(L7,"Aufbau","The Aufbau principle states that electrons fill orbitals:",
    ["From highest to lowest energy","In order of increasing energy","Randomly","By spin only"],1,"Electrons fill orbitals in order of increasing energy (Aufbau = building up).","Easy")
mcq(L7,"Hund","Hund's rule says that electrons in degenerate (equal-energy) orbitals:",
    ["Pair up first","Occupy separate orbitals with parallel spins before pairing","All enter one orbital","Always have opposite spins"],1,"Hund's rule: each degenerate orbital is singly occupied (parallel spins) before any pairing.")
mcq(L7,"Electronic configuration","The electronic configuration 1s² 2s² 2p⁶ 3s¹ corresponds to which element?",
    ["Ne (10)","Na (11)","Mg (12)","Al (13)"],1,"The sum of superscripts = 11 electrons → sodium.")
mcq(L7,"Pauli","According to the Pauli exclusion principle, an orbital can hold a maximum of:",
    ["1 electron","2 electrons with opposite spins","2 electrons with the same spin","6 electrons"],1,"Each orbital holds at most two electrons and they must have opposite spins.")
mcq(L7,"Electron configuration","The number of electrons that can be accommodated in the p subshell is:",
    ["2","6","10","14"],1,"A p subshell has 3 orbitals × 2 electrons = 6.")
mcq(L7,"Electron configuration","The number of orbitals in an s, p, d, and f subshell respectively are:",
    ["1, 3, 5, 7","1, 2, 3, 4","2, 6, 10, 14","1, 4, 9, 16"],0,"An orbital holds up to 2 electrons; s=1, p=3, d=5, f=7 orbitals.")
flash(L7,"Aufbau principle","Electrons occupy orbitals in order of increasing energy.")
flash(L7,"Hund's rule","Fill each degenerate orbital singly (parallel spins) before pairing electrons.")
flash(L7,"Pauli exclusion principle","Max two electrons per orbital, with opposite spins.")
flash(L7,"Orbital capacity","s=2, p=6, d=10, f=14 electrons.")

# ---------------- Lesson 1.8 Periodic properties ----------------
mcq(L8,"Periodic table","Elements in the same group of the periodic table have the same number of:",
    ["Shells","Valence electrons","Neutrons","Protons"],1,"Group (vertical column) elements share the same number of valence electrons, hence similar chemistry.","Easy")
mcq(L8,"Periodic trends","Across a period from left to right, the atomic radius generally:",
    ["Increases","Decreases","Stays the same","First increases then decreases"],1,"Nuclear charge increases across a period, pulling electrons closer, so atomic radius decreases.")
mcq(L8,"Ionisation energy","The first ionisation energy is the energy needed to:",
    ["Add an electron to an atom","Remove the most loosely held electron from a gaseous atom","Split a nucleus","Form an ionic bond"],1,"First ionisation energy removes the outermost electron from a neutral gaseous atom.")
mcq(L8,"Electronegativity","Electronegativity is a measure of an atom's ability to:",
    ["Lose electrons","Attract electrons in a chemical bond","Gain neutrons","Form cations"],1,"Electronegativity is the tendency of an atom to attract bonding electrons toward itself.")
mcq(L8,"Metals vs nonmetals","Metals are generally characterised by:",
    ["High ionisation energy and small radius","Low ionisation energy and tendency to lose electrons","Tendency to gain electrons","Being brittle insulators"],1,"Metals have low ionisation energy and tend to lose electrons to form cations.")
mcq(L8,"Groups","Elements in group 1 (alkali metals) are:",
    ["Non-metals","Highly reactive metals that lose one electron","Halogens","Noble gases"],1,"Alkali metals have one valence electron and are reactive metals.")
flash(L8,"Group / period","Group = vertical column (same valence electrons); Period = horizontal row (same number of shells).")
flash(L8,"Atomic radius trend","Decreases across a period; increases down a group.")
flash(L8,"Ionisation energy","Energy to remove an electron from a gaseous atom; increases across a period.")
flash(L8,"Electronegativity","Tendency of an atom to attract bonding electrons; high for non-metals like F, Cl.")

# ---------------- Lesson 9 & 10: terms/equations quick checks ----------------
for lid,con in [(L9,"Key terms"),(L10,"Key equations")]:
    mcq(lid,con,"An atom is defined as the:",
       ["Smallest particle of an element that takes part in chemical reactions","Largest particle of a compound","Mixture of molecules","Subatomic particle with no charge"],0,
       "An atom is the smallest unit of an element that retains its chemical properties and takes part in chemical reactions.","Easy")
    tf(lid,con,"Mass number (A) = number of protons + number of neutrons.",True,"By definition A = Z + N.")
    mcq(lid,con,"The value of Planck's constant h used in E = hν is approximately:",
       ["6.626e-34 J·s","3.0e8 m/s","1.602e-19 C","6.02e23"],0,"Planck's constant h ≈ 6.626e-34 J·s.")
    flash(lid,"Atom","Smallest particle of an element that can take part in a chemical reaction.")
    flash(lid,"E = hν","Energy of a photon; h = Planck's constant, ν = frequency.")
    flash(lid,"A = Z + N","Mass number = protons + neutrons.")

print("Inserted approved questions & flashcards for Chemistry Grade 11, Unit 1")
print("Lessons:", len(lessons))
