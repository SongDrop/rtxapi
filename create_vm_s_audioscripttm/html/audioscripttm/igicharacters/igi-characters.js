var characters = [
  {
    name: "David Jones",
    img: "./igicharacters/davidjones.png",
    description:
      "David Jones is a former SAS soldier turned freelance operative. As the protagonist of Project IGI, he is tasked with infiltrating enemy bases, gathering intelligence, and neutralizing high-value targets. Skilled in stealth, firearms, and tactical planning, Jones is a one-man army against global threats.",
    actor: "Stephen Critchlow",
    abilities: [
      {
        name: "Stealth Operations",
        description:
          "Jones excels in stealth missions, using silent takedowns and evasion techniques to remain undetected.",
      },
      {
        name: "Advanced Weapons Handling",
        description:
          "Trained in various firearms and explosives, Jones is proficient in both close-quarters combat and long-range engagements.",
      },
      {
        name: "Hacking and Infiltration",
        description:
          "Capable of bypassing security systems and hacking terminals to gain access to restricted areas.",
      },
    ],
    trivia: [
      "David Jones' character was inspired by real-life covert operatives and SAS training techniques.",
      "He rarely speaks during missions, preferring to let his actions do the talking.",
      "The character's design was influenced by action movies of the late '90s and early 2000s.",
    ],
    history: [
      "Jones is assigned to retrieve stolen nuclear technology and prevent it from falling into enemy hands.",
      "He partners with Anya, an intelligence officer, who provides crucial mission support and information.",
      "Throughout his missions, Jones uncovers a deeper conspiracy involving rogue military factions and arms dealers.",
    ],
  },
  {
    name: "Anya",
    img: "./igicharacters/anya.png",
    description:
      "Anya is a top intelligence officer who provides mission briefings, tactical support, and strategic insights to David Jones. She serves as his main point of contact throughout his operations, guiding him through dangerous territories and enemy compounds.",
    actor: "Kim Romer",
    abilities: [
      {
        name: "Mission Coordination",
        description:
          "Anya provides real-time intelligence and strategic updates, ensuring Jones has the necessary information to complete objectives.",
      },
      {
        name: "Surveillance and Reconnaissance",
        description:
          "Using satellite feeds and advanced tracking systems, Anya monitors enemy movements and potential threats.",
      },
      {
        name: "Cybersecurity Expertise",
        description:
          "She can hack into enemy communications, disrupt security systems, and decrypt classified documents.",
      },
    ],
    trivia: [
      "Anya's voice and character design were updated in later versions of Project IGI.",
      "She plays a crucial role in guiding the player through the toughest missions.",
      "Unlike Jones, Anya rarely engages in direct combat but is vital for intelligence gathering.",
    ],
    history: [
      "Anya assists Jones in tracking down stolen nuclear components and uncovering terrorist plots.",
      "She works closely with intelligence agencies, providing crucial data to prevent global conflicts.",
      "Throughout the missions, she and Jones develop a strong professional bond, relying on each other to survive and succeed.",
    ],
  },
  {
    name: "Jach Priboi",
    img: "./igicharacters/Jack_Priboi.jpg",
    description:
      "Jach Priboi is a Soviet arms dealer and the uncle of Josef Priboi. He is a central figure in the game's plot, as his dealings and connections are pivotal to the unfolding events.",
    actor: "Unknown",
    abilities: [
      {
        name: "Arms Dealing",
        description:
          "Jach has extensive networks and knowledge in the black market arms trade.",
      },
      {
        name: "Strategic Planning",
        description:
          "He is adept at orchestrating complex deals and evading law enforcement.",
      },
    ],
    trivia: [
      "Jach Priboi's character adds depth to the game's narrative, representing the intricate world of arms trading.",
      "His interactions with other characters drive much of the game's storyline.",
    ],
    history: [
      "Jach's arms dealings attract the attention of international intelligence agencies.",
      "His relationship with his nephew, Josef, complicates the dynamics of the game's events.",
    ],
  },
  {
    name: "Josef Priboi",
    img: "./igicharacters/Josef_Priboi.png",
    description:
      "Josef Priboi is the nephew of Jach Priboi and is involved in his uncle's arms dealing operations. He becomes a person of interest due to his knowledge of stolen nuclear warheads.",
    actor: "Unknown",
    abilities: [
      {
        name: "Information Brokerage",
        description:
          "Josef possesses critical information about illicit arms deals and stolen weaponry.",
      },
      {
        name: "Evasion",
        description:
          "Skilled in avoiding capture, Josef employs various tactics to stay under the radar.",
      },
    ],
    trivia: [
      "Josef's capture and interrogation are key objectives in the game's early missions.",
      "His knowledge serves as a catalyst for the protagonist's subsequent missions.",
    ],
    history: [
      "Josef's involvement in arms dealing leads to his capture by military forces.",
      "Information extracted from Josef sets the protagonist on a path to uncover larger threats.",
    ],
  },
  {
    name: "Ekk",
    img: "./igicharacters/Ekk.png",
    description:
      "Ekk is a homicidal Russian woman with intentions to initiate nuclear warfare in Europe. She serves as one of the primary antagonists in the game.",
    actor: "Unknown",
    abilities: [
      {
        name: "Leadership",
        description:
          "Ekk commands a group of loyal followers and orchestrates complex operations.",
      },
      {
        name: "Strategic Warfare",
        description:
          "She has a deep understanding of nuclear weapons and their deployment.",
      },
    ],
    trivia: [
      "Ekk's motivations are driven by a desire to reshape the geopolitical landscape.",
      "Her confrontations with the protagonist are among the game's most challenging encounters.",
    ],
    history: [
      "Ekk's plans involve the acquisition and deployment of nuclear warheads.",
      "She engages in multiple confrontations with the protagonist, showcasing her tactical prowess.",
    ],
  },
  {
    name: "Captain Harrison",
    img: "./igicharacters/Harrison.png",
    description:
      "Captain Harrison is a commander of allied troops and an ex-Green Beret in the US Army Special Forces. He provides support to the protagonist during various missions.",
    actor: "Unknown",
    abilities: [
      {
        name: "Tactical Command",
        description:
          "Harrison excels in leading troops and coordinating military operations.",
      },
      {
        name: "Combat Support",
        description:
          "He offers essential backup and resources during critical mission phases.",
      },
    ],
    trivia: [
      "Captain Harrison's military background complements the protagonist's skill set.",
      "His presence provides a sense of camaraderie and support in hostile environments.",
    ],
    history: [
      "Harrison collaborates with the protagonist to thwart Ekk's nuclear ambitions.",
      "His strategic insights prove invaluable during high-stakes missions.",
    ],
  },
  {
    name: "Nagochi",
    img: "./igicharacters/nagochi.png",
    description:
      "Nagochi is a highly skilled special forces operative and a key member of Captain Harrison’s team. Known for his stealth abilities and combat expertise, he plays a crucial role in reconnaissance and infiltration missions.",
    actor: "Unknown",
    abilities: [
      {
        name: "Stealth Infiltration",
        description:
          "Nagochi is an expert in silent takedowns and evasion techniques, making him ideal for covert operations.",
      },
      {
        name: "Hand-to-Hand Combat",
        description:
          "Trained in close-quarters combat, he can neutralize enemies without raising alarms.",
      },
      {
        name: "Advanced Reconnaissance",
        description:
          "Capable of scouting enemy locations and providing valuable intelligence.",
      },
    ],
    trivia: [
      "Nagochi's name suggests an Asian background, possibly linked to elite special forces training.",
      "He is one of the most disciplined and precise members of Harrison’s squad.",
    ],
    history: [
      "Nagochi joined Harrison’s team as a stealth specialist for high-risk missions.",
      "He has been instrumental in gathering intel on enemy movements and fortifications.",
    ],
  },
  {
    name: "Skinner",
    img: "./igicharacters/skinner.png",
    description:
      "Skinner is the heavy weapons specialist of Captain Harrison’s team. Known for his brute strength and aggressive combat style, he is deployed in high-risk missions that require overwhelming firepower.",
    actor: "Unknown",
    abilities: [
      {
        name: "Heavy Weapons Mastery",
        description:
          "Skinner is proficient with machine guns, explosives, and high-caliber weaponry.",
      },
      {
        name: "Defensive Tactics",
        description:
          "Provides cover fire and protection for his team during assaults.",
      },
      {
        name: "Breach and Clear",
        description:
          "Specializes in breaking through enemy defenses and securing high-threat areas.",
      },
    ],
    trivia: [
      "Skinner is often the first to charge into combat, making him one of the most fearless operatives.",
      "Rumored to have served in multiple high-risk war zones before joining Harrison’s team.",
    ],
    history: [
      "Skinner was recruited for his unmatched combat skills and ability to handle high-pressure situations.",
      "He played a key role in multiple direct assaults against enemy strongholds.",
    ],
  },
  {
    name: "Leonard",
    img: "./igicharacters/leonard.png",
    description:
      "Leonard is the communications and tactical support expert of Captain Harrison’s team. He ensures secure communication channels and provides real-time mission updates to the squad.",
    actor: "Unknown",
    abilities: [
      {
        name: "Electronic Warfare",
        description:
          "Leonard can tap into enemy communications and disrupt security systems.",
      },
      {
        name: "Mission Coordination",
        description:
          "Provides battlefield intelligence, tracking enemy movements and securing extraction routes.",
      },
      {
        name: "Strategic Planning",
        description:
          "Works closely with Harrison to devise tactical approaches for complex missions.",
      },
    ],
    trivia: [
      "Leonard rarely engages in combat but plays a vital role in mission success.",
      "His quick thinking and ability to adapt to changing scenarios make him an invaluable asset.",
    ],
    history: [
      "Leonard was brought onto Harrison’s team due to his expertise in cybersecurity and military communications.",
      "His intelligence gathering has prevented several mission failures by detecting threats in advance.",
    ],
  },
];
