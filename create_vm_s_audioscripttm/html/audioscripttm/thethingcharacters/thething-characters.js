var characters = [
  {
    name: "Blake",
    img: "./characters/Blake.png",
    description:
      "Captain J.F. Blake is an American soldier and commanding officer of the Arctic Marines' Bravo team, featured as the main protagonist in the 2002 video game The Thing. Blake leads his team to investigate U.S. Outpost 31 after the events of the film. He is portrayed by voice actor Per Solli. Blake navigates through dangerous terrain, battling both the alien creatures known as the Things and various conspiracies, eventually uncovering a government plot to weaponize the Thing virus. Throughout the game, it is implied that Blake has developed an immunity to the Thing's assimilation process.",
    actor: "Per Solli",
    abilities: [
      {
        name: "Healing",
        description:
          "Blake has the ability to heal the team, but this is limited compared to a dedicated Medic class.",
      },
      {
        name: "Junction Box Fixing",
        description:
          "Blake can fix Basic Junction boxes, though the Engineer class is better suited for advanced repairs.",
      },
      {
        name: "Combat Skills",
        description:
          "Blake excels in combat, suited to the Soldier class with the best weapon accuracy and courage.",
      },
    ],
    trivia: [
      "Blake's full name is J.F. Blake, a possible nod to R.J. MacReady from the original film.",
      "Blake is immune to assimilation by the Thing, potentially due to contact with the alien lifeform.",
      "Blake is the only member of the team who can speak Norwegian, though this is not explicitly used in the game.",
      "Several unused quotes in the game files hint at Blake's frustration with reading Norwegian and dealing with game mechanics like locks and access codes.",
    ],
    history: [
      "Blake leads Bravo Team to investigate U.S. Outpost 31 and discovers the Thing's infiltration.",
      "He uncovers the body of Childs and learns that MacReady is missing.",
      "Blake continues the investigation at the Norwegian camp and eventually learns about the 'Cloud virus' and a government conspiracy.",
      "He confronts Colonel Whitley, who has injected himself with a version of the Thing virus, and fights to stop a global outbreak.",
    ],
  },

  {
    name: "Austin",
    img: "./characters/Austin.png",
    description:
      "Austin is a Gen Inc researcher and Soldier stationed at the Weapons Laboratory, who becomes assimilated by the Thing. He works with engineers and a medic to develop an anti-Thing virus in the underground covert Weapons Laboratory. After being assimilated, Austin deceives Blake by locking him in a gas-filled room, before retreating to a weapons research lab where he slowly bleeds to death. Austin's identity is hinted at through computer journals and his designation as 'Austin3' in the squad menu.",
    actor: "N/A",
    abilities: [
      {
        name: "Deception",
        description:
          "Austin tricks Blake into a trap by urging him to investigate a terminal that he pretends to be unable to operate.",
      },
      {
        name: "Assimilation",
        description:
          "If Blake reaches Austin before he dies, Austin will immediately assimilate. There's barely any time to perform a blood test before this happens.",
      },
      {
        name: "Squad Member",
        description:
          "When Austin is assimilated, he can still fight alongside the team, though he will mysteriously disappear after the current level.",
      },
    ],
    trivia: [
      "Austin's name in the squad menu is displayed as 'Austin3' when the player approaches him as he bleeds out.",
      "Despite wearing an Engineer's uniform, Austin is designated as a Soldier, hinting he may be an Imitation, similar to other characters like Carter and Guy.",
      "There is a method (though highly inconsistent) to prevent Austin from assimilating by performing a specific set of commands just before reaching him. If successful, he will act as an assimilated squad member and help fight the Things.",
      "Austin can either bleed out in the weapons research lab or burst out if fired at from the Observation Area's sniper camera gun.",
    ],
    history: [
      "Austin is part of a team researching an anti-Thing virus at the Gen Inc. Weapons Laboratory.",
      "He is assimilated by the Thing, deceiving Blake into entering a trap and locking himself in the weapons research lab.",
      "He slowly bleeds to death, but if Blake reaches him in time, Austin will assimilate and attempt to hide his true nature.",
    ],
  },

  {
    name: "Burrows",
    img: "./characters/Burrows.png",
    description:
      "Burrows was an Engineer assigned to the Arctic Marines' Bravo Team to investigate the U.S. Outpost 31 in 1982. He appears in the 2002 video game *The Thing*. Along with his teammates, Burrows discovered an extraterrestrial UFO, a Thing corpse, and the frozen body of Childs. After the outpost's destruction, he continued his mission to investigate the Norwegian outpost alongside Captain Blake.",
    actor: "N/A",
    abilities: [
      {
        name: "Engineering",
        description:
          "Burrows is an Engineer, capable of performing bypasses and repairs, helping the team with technical tasks.",
      },
    ],
    trivia: [
      "Burrows is calm and collected, offering his assistance to Blake in the early stages of the mission.",
      "He is part of Bravo Team, which was sent to investigate U.S. Outpost 31 after losing radio contact with the facility.",
    ],
    history: [
      "Burrows is part of the team investigating the mysterious events at U.S. Outpost 31 in Antarctica after losing contact with the station in the winter of 1982.",
      "Upon discovering a UFO, a Thing corpse, and the frozen body of Childs, the Bravo Team is ordered to destroy the outpost with C4 charges.",
      "Following the destruction, Burrows joins Captain Blake in attempting to assist Alpha Team at the Norwegian outpost after all contact with them is lost.",
    ],
  },

  {
    name: "Carter (Engineer)",
    img: "./characters/Carter(engineer).png",
    description:
      "Carter was an Engineer assigned to the Arctic Marines' Alpha Team, tasked with investigating the Norwegian Thule Station. He appears in the 2002 video game *The Thing*. After his team is attacked by assumed friendlies, Carter becomes paranoid and wounded. J.F. Blake aids him, and together they discover that Carter and another team member, Cruz, have been assimilated by the Thing. They are both revealed as imposters and are ultimately destroyed by Blake and Pierce.",
    actor: "N/A",
    abilities: [
      {
        name: "Engineering",
        description:
          "Carter is an Engineer, though he does not fully utilize his skills as his true nature is revealed during the mission.",
      },
      {
        name: "Infiltration",
        description:
          "Carter is revealed to be an imposter after interacting with him and Cruz, ultimately being exposed as a Thing.",
      },
    ],
    trivia: [
      "Carter shares the same name with the Soldier character Carter, though there is no explanation for the shared name.",
      "Carter is scripted to be infected after returning to Pierce with blood test hypos and will reveal himself as a Thing on a set timer.",
      "Unlike Cruz, Carter's transformation into a Thing is timed, and can be avoided through a glitch to skip the hypo use.",
    ],
    history: [
      "Carter is part of Alpha Team, sent to investigate the Thule Station. He is discovered by Blake after the team is attacked by people who were assumed to be allies.",
      "Blake helps Carter and gives him a weapon, but as the group progresses, Carter and Cruz are revealed to be Things and attack the group before being destroyed by Blake and Pierce.",
    ],
  },

  {
    name: "Carter (Soldier)",
    img: "./characters/Carter(soldier).jpg",
    description:
      "Carter is a Gen Inc researcher and Soldier, though he originally appeared to be a Medic, stationed at the Strata Medical Laboratory in Antarctica. He appears in the 2002 video game *The Thing*. Carter is initially found trapped in a chamber during the outbreak of the Thing, where he is rescued by Blake. However, he is later revealed to be an imposter and is killed by Blake and his team.",
    actor: "N/A",
    abilities: [
      {
        name: "Combat",
        description:
          "Carter can be armed and assist in combat, though his true nature as an imitation will be revealed during gameplay.",
      },
      {
        name: "Imposter Infiltration",
        description:
          "Carter is an imitation of a human, designed to deceive Blake and the rest of the team before revealing himself as a Thing.",
      },
    ],
    trivia: [
      "Carter wears a Medic's uniform, but is actually designated as a Soldier, a common trait for the Imitations in the game who often wear incorrect uniforms.",
      "He shares the same name as Carter (Engineer), but the reason for this shared name is unknown.",
      "Unlike many infected NPCs, Carter can still speak and is not completely silent after being assimilated.",
      "It is possible to prevent Carter from transforming into a Thing using a specific strategy where he is kept in the squad, given a weapon, and certain actions are timed carefully.",
      "Sometimes, after recruiting Carter, he can test negative on a blood test despite being infected, depending on how quickly he is recruited into the squad.",
      "Carter has a glitch where, after a security switch sequence cutscene, he can appear human while acting like an imposter, spitting venom and growling like a Thing.",
    ],
    history: [
      "Carter is discovered by Blake trapped in a chamber during the outbreak of the Thing at the Strata Medical Laboratory.",
      "After Blake rescues him, Carter initially helps and can be recruited into the squad. However, it is soon revealed that Carter is actually an imposter and transforms into a Thing, leading to his death at the hands of Blake and the team.",
      "In the Remastered version of the game, Carter is given a Soldier uniform instead of a Medic's outfit, and his behavior becomes more aggressive as his true nature is revealed.",
    ],
  },

  {
    name: "Cohen",
    img: "./characters/Cohen.jpg",
    description:
      "Cohen is a Gen Inc researcher and Medic stationed at the Weapons Laboratory in Antarctica. He appears in the 2002 video game *The Thing*. He was seen running from Whitley’s Black Ops soldiers and later teamed up with Blake to fight against them and the Things. Though he disappears after the encounter, it is assumed that he died in the destruction of the facility.",
    actor: "N/A",
    abilities: [
      {
        name: "Medic",
        description:
          "Cohen serves as a Medic and can heal the team, much like the other Medics in the game.",
      },
      {
        name: "Impersonation Resistance",
        description:
          "Cohen remains human as long as he is not exposed too much to The Thing. If sufficiently damaged, he becomes infected and transforms.",
      },
    ],
    trivia: [
      "Cohen is involved in researching an anti-Thing virus, working alongside Ryan and Stolls at the Weapons Laboratory.",
      "He disappears after the Weapons Laboratory encounter and is assumed to have died during the facility’s destruction.",
      "Cohen can be kept alive until the end, but he will disappear in the next area.",
      "Despite being a Medic, Cohen can become infected if exposed to the Thing enough times.",
    ],
    history: [
      "Cohen was first encountered by Blake running away from Whitley’s Black Ops soldiers. After teaming up with Blake, they fought the Black Ops and the Things, making their way into the Weapons Laboratory.",
      "After the battle, Cohen’s fate is unclear as he disappears. It is suggested that he perished in the subsequent destruction of the Weapons Laboratory.",
      "His journal entries reveal that he worked with Ryan and Stolls on an anti-Thing virus, but it is unclear what happened to him after he was separated from his team.",
    ],
  },

  {
    name: "Collins",
    img: "./characters/Collins.jpg",
    description:
      "Collins is an Engineer assigned to the Arctic Marines' Alpha Team and tasked with investigating the Norwegian Outpost. He appears in the 2002 video-game The Thing.",
    actor: "N/A",
    abilities: [
      {
        name: "Imitation",
        description:
          "Despite initially appearing to help, Collins reveals himself as an imitation later in the game.",
      },
      {
        name: "Junction Box Repair",
        description:
          "Collins is able to repair the junction box, granting Blake access to the Pyron Sub Facility.",
      },
    ],
    trivia: [
      "Collins and Larsen, a Norwegian from the intro, wear the same uniform, which could lead to confusion about their identities.",
    ],
    history: [
      "While exploring the Pyron Hangar, Collins barricaded himself in a room to avoid the Things. Blake entered the hangar through an air duct and rescued him.",
      "After clearing the creatures in the hangar, Collins repaired the building's junction box, enabling Blake to access the Pyron Sub Facility.",
      "However, Collins later revealed himself to be an imitation, and was subsequently burned by Blake.",
    ],
  },

  {
    name: "Cruz",
    img: "./characters/Cruz.png",
    description:
      "Cruz is a Soldier assigned to the Arctic Marines' Alpha Team, tasked with investigating the Thule Station. He appears in the 2002 video game *The Thing*. Cruz is initially found separated from his squad and locked in an ice-block room. He claims to have heard nothing from his team for some time, but is later revealed to be an imposter and transforms into a Thing.",
    actor: "N/A",
    abilities: [
      {
        name: "Soldier",
        description:
          "As a soldier, Cruz is trained for combat, though his true loyalty is revealed to be to the Thing once he is assimilated.",
      },
    ],
    trivia: [
      "Cruz is one of the characters who is revealed to be an imposter during the course of the game.",
      "If the player uses a glitch, Cruz can help kill the Carter-Thing before he transforms, but he must still be killed after assimilating.",
      "Cruz's transformation into a Thing can be delayed by not using the blood test hypos, allowing him to assist in combat before his eventual assimilation.",
    ],
    history: [
      "Cruz is found locked in an ice-block room at the Norwegian Outpost, where he explains that he was separated from his team and hasn't heard from them in a while. He and Blake go on to meet Pierce and discover Carter and Cruz's betrayal.",
      "After a series of blood tests, it is revealed that both Cruz and Carter are imposters, and they transform into Things. Blake and Pierce are forced to deal with them, incinerating both before they can continue.",
    ],
  },

  {
    name: "Dixon",
    img: "./characters/Dixon.png",
    description:
      "Dixon is a Gen Inc member stationed at the Strata Medical Laboratory in Antarctica. He is initially stranded during the outbreak of the Thing but is rescued by Blake. Though he aligns with Blake and his team, his involvement leads him to become a target of Whitley's extermination list. Dixon is ultimately killed by an explosion caused by a time bomb set by Whitley, leading to the destruction of the Strata Medical Laboratory.",
    actor: "N/A",
    abilities: [
      {
        name: "Survivor",
        description:
          "Dixon is a resilient member of the team who fights alongside Blake against both the Things and Whitley's Black Ops units. His trust in Blake helps him survive much longer than expected in a facility overrun by monsters.",
      },
    ],
    trivia: [
      "Dixon is one of the characters who can succumb to the infection and burst out as a Thing if attacked enough by the Things.",
      "He is part of a team that fights through the Strata Medical Laboratory, uncovering the presence of imitations and trying to escape the devastation of the facility.",
      "Despite surviving the chaos and facing numerous threats, Dixon's story ends tragically when he is killed by an explosion triggered by Whitley's sabotage.",
    ],
    history: [
      "Dixon is rescued by Blake after the initial outbreak of the Thing at the Strata Medical Laboratory. The two form an alliance, and Dixon helps Blake fight against both the Things and Whitley's Black Ops units.",
      "Dixon's efforts with Blake's team ultimately lead them to confront a time bomb set by Whitley. Unfortunately, Dixon perishes in the explosion that destroys the Strata Medical Laboratory, while Blake narrowly escapes to continue the fight.",
    ],
  },

  {
    name: "Falchek",
    img: "./characters/Falchek.png",
    description:
      "Falchek is a Gen Inc researcher and Medic stationed at the Strata Medical Laboratory in Antarctica. During the initial outbreak of the Thing, he barricades himself in a chamber, but Blake rescues him. Although he becomes an ally of Blake and helps fight the Things and Whitley's Black Ops, he ultimately becomes an Imitator and is killed by Blake.",
    actor: "N/A",
    abilities: [
      {
        name: "Medic",
        description:
          "Falchek serves as a medic in Blake's team, helping heal squad members and fight the Things.",
      },
    ],
    trivia: [
      "Falchek's face was modeled after Andrew Curtis, the Lead Designer of The Thing (2002), according to a developer interview.",
      "Many of the NPCs and squad members in the game are based on photos taken from the developers, adding a personal touch to their designs.",
    ],
    history: [
      "During the outbreak of the Thing in the Strata Medical Laboratory, Falchek barricades himself. He is rescued by Blake, who gains his trust. Falchek helps Blake and the team fight both the Things and Whitley's Black Ops forces.",
      "However, despite his initial trustworthiness, Falchek eventually becomes an Imitator. Blake is left with no choice but to kill him to prevent further danger.",
    ],
  },

  {
    name: "Fisk",
    img: "./characters/Fisk.png",
    description:
      "Fisk is a Soldier and test subject incarcerated at the Strata Medical Laboratory in Antarctica. Initially found imprisoned, he aids Blake and his team in escaping the facility. Despite helping Blake and others, Fisk's fate is uncertain, though he likely perished during the destruction of the facility or was assimilated by the Thing.",
    actor: "N/A",
    abilities: [
      {
        name: "Soldier",
        description:
          "Fisk serves as a soldier in Blake's squad, contributing to combat and assisting in escaping the Strata Medical Laboratory.",
      },
    ],
    trivia: [
      "Fisk's cutscene where he provides the combination for the laser switches was originally meant for a cut character, Ryder, whose role was merged with Fisk due to budget and time constraints.",
      "In the game files, Fisk's head can be found stored in a formaldehyde tank, examined by Whitley.",
      "Fisk can become a Thing if sufficiently exposed to Scuttler attacks, and he shares a burst-out assimilation model with Parnevik, though it features clipping and missing neck sections in the model.",
    ],
    history: [
      "Fisk is found imprisoned in one of Strata Medical Laboratory's holding cells, where he was being used as a test subject. He later aids Blake, Falchek, and Dixon in escaping the facility, making their way through the furnace room and tunnel system. However, Fisk disappears after the team proceeds to the Strata Furnace level, and his ultimate fate remains unknown.",
      "It is presumed that Fisk was either killed by the Thing or perished due to the bomb set by Whitley. His disappearance was likely due to a bug, which was fixed in the Remastered version.",
    ],
  },

  {
    name: "Guy",
    img: "./characters/Guy.jpg",
    description:
      "Guy is a Gen Inc researcher and Soldier stationed at the Strata Medical Laboratory in Antarctica. He quickly reveals himself to be an imitation upon being found by Blake and his team in the furnace rooms.",
    actor: "N/A",
    abilities: [
      {
        name: "Imitation",
        description:
          "Despite initially appearing human, Guy is an imitation and reveals his true form upon being approached by Blake.",
      },
    ],
    trivia: [
      "Guy will quickly reveal himself as an imitation, similar to characters like Parnevik, Stanmore, and Carter (Soldier).",
      "Like many imitations, Guy remains silent and does not speak.",
      "He trusts Blake 100% from the beginning, showing no suspicion.",
      "Guy will burst from a long distance atop a staircase after a short time, and there's little time to recruit him before he bursts.",
      "Although he is wearing an engineer's uniform, Guy is designated as a soldier in the squad menu.",
    ],
    history: [
      "Guy was found by Blake and his team in the furnace room of the Strata Medical Laboratory. Positioned atop a staircase outside the Furnace Rupture, he quickly reveals himself as an imitation and is immediately disposed of by the team.",
      "His burst transformation is scripted to happen when approached, even though he can initially be sniped and killed like a regular human.",
    ],
  },

  {
    name: "Hanson",
    img: "./characters/Hanson.png",
    description:
      "Hanson is a test subject who was detained and experimented on in the Strata Medical Laboratory in Antarctica. He is a minor character in the 2002 video game, The Thing.",
    actor: "N/A",
    abilities: [
      {
        name: "Escape Attempt",
        description:
          "Hanson attempted to escape by using a vent in his cell, which hints Blake toward an escape route.",
      },
    ],
    trivia: [
      "Hanson's body is a generic corpse model used throughout the game, meaning he is not a fully fleshed-out NPC.",
      "His journal provides hints for players, especially for inspecting Cell #3 for an escape route.",
      "Hanson's corpse can be found mauled by a Walker patrol or shot by an automatic turret in the hallway.",
    ],
    history: [
      "Hanson was held in Cell #3 of the Strata Medical Laboratory, where he wrote a journal detailing his fear of the situation and the disappearances of people around him.",
      "He expressed concern over strange noises and eventually decided to escape using a vent in his cell, hinting at a potential route for Blake.",
      "Hanson's body is found in a hallway, suggesting he was killed by a Walker or an automatic turret.",
    ],
  },

  {
    name: "Hawk",
    img: "./characters/Hawk.png",
    description:
      "Hawk (also known as 'Hawke' in some files) is an unused character from the 2002 video game 'The Thing.' He has complete voice files found in the game's data folder, but his character was ultimately cut from the final version of the game.",
    history: [
      "Hawk was meant to be an NPC that the player could recruit, similar to other characters in the game.",
      "He has a scripted encounter where he mentions rescuing Dr. Faraday: 'Dr. Faraday is trapped in Chamber 9. Hobson and myself have DNA scan access, we need to get to Chamber 9!'",
      "Hawk would have likely been featured in the same area as Hobson, but the idea was ultimately scrapped.",
    ],
    trivia: [
      "Hawk's dialogue suggests that he may have originally been the Unnamed Medic, as he references rescuing Dr. Faraday in the Pyron Submersible Facility.",
      "Although he has voice files, Hawk doesn't have any face models in the game files, meaning if he had been implemented, he would have lacked a visual representation.",
      "Hawk is one of the few known cut characters, along with Hobson and Ryder, whose files remain in the game's folders.",
    ],
    gallery: ["Hawk's voice files (found in the 'english.pak' folder)."],
  },

  {
    name: "Hobson",
    img: "./characters/Hobson.png",
    description:
      "Hobson is an unused character from the 2002 video game 'The Thing.' He has complete voice files found in the game's data folder, but his character was ultimately cut from the final version of the game.",
    history: [
      "Hobson was intended to be an NPC that the player could recruit, similar to other characters in the game.",
      "He is mentioned to have been in the same area as Hawk, and would have had a scripted encounter in which he would provide dialogue regarding rescuing Dr. Faraday: 'Dr. Faraday is trapped in Chamber 9. Hawk and myself have DNA scan access, we need to get to Chamber 9!'",
      "It appears Hobson was meant to help the player by granting access to the testing chambers needed to rescue Dr. Faraday, but this idea was scrapped.",
    ],
    trivia: [
      "Hobson's dialogue suggests that he may have originally been the Unnamed Medic, as he references rescuing Dr. Faraday in the Pyron Submersible Facility.",
      "Although he has voice files, Hobson doesn't have any face models in the game files, implying that if he had been implemented, he would have lacked a visual representation.",
      "Hobson is one of the few known cut characters, along with Hawk and Ryder, whose files remain in the game's folders.",
    ],
    gallery: ["Hobson's voice files (found in the 'english.pak' folder)."],
  },
  {
    name: "Iversen",
    img: "./characters/Iversen.jpg",
    description:
      "Iversen is a Radio Operator and Soldier (presumably also a Medic) stationed at the Norwegian Research Center in Antarctica. He appeared in the 2002 video game 'The Thing,' but was not a recruitable character through normal gameplay.",
    history: [
      "Iversen is first seen in the intro cutscene of the game via CCTV footage, where he is shown asking for help and sitting against a counter in the Norwegian Research Center.",
      "He is attacked by a Full Walker along with Larsen, and later seemingly assimilated, chased by Blake and his team to the Pyron Hangar, where he bursts into the Hangar Rupture and is eventually defeated by Blake.",
      "An unused document found in the game files (thingstrings_en.bt) mentions the Norwegian camp situation and Iversen by name, providing further context for his character.",
    ],
    how_to_get_in_team: [
      "Iversen cannot normally be recruited in the game but can be acquired via mods or a specific bug. In the Norwegian Medi-Center level, players can use flame grenades to trigger a bug that spawns Iversen, allowing him to join the team.",
      "Once acquired, Iversen trusts the player 100% from the start and is listed as a Soldier in the squad menu. However, he doesn't have any walk routes in the level and can only help fight the Assimilant from the fuel hut.",
    ],
    trivia: [
      "Iversen’s name can only be known by spawning him through mods or accessing the game files. His name is sometimes misspelled as 'Iverson' in the game files.",
      "He is listed as a Soldier in the squad menu when recruited through mods. Some suggest he may have originally been intended as a Medic due to his uniform, which features a red cross.",
      "Iversen's name has been mistaken for 'Larsen' because of his scream in the intro, but it's confirmed that Iversen and Larsen are different characters.",
      "Although Iversen tests negative in blood tests if acquired through the bug, he is actually already infected story-wise.",
      "The journal found in the game mentions Iversen's grief over the death of his brother during the Thing attack, which heavily impacted him.",
    ],
    gallery: [
      "Iversen as an NPC squad mate, spawned via mods.",
      "Iversen in the squad menu, acquired through a mod. Notice how he's listed as a Soldier.",
      "Iversen at the Norwegian Medi-Center, acquired through the flame grenade bug.",
      "Iversen acquired in the squad menu through the flame grenade bug, at the Norwegian Medi-Center.",
    ],
  },
  {
    name: "Larsen",
    img: "./characters/Larsen.png",
    description:
      "Larsen was a researcher stationed at the Norwegian Research Center in Antarctica. He appeared in the 2002 video game 'The Thing,' though his role is limited to a single cutscene.",
    history: [
      "In the game's introductory cutscene, Larsen is seen investigating a disturbance in the Norwegian Research Center's mess hall. He is called by Iversen, a fellow Norwegian Radio Operator, who is injured and in need of help.",
      "Larsen attempts to assist Iversen but is attacked by a Full Walker. Despite shooting it and attempting to fend it off, he is mauled and killed by the creature. The Walker proceeds to attack and assimilate Iversen, as the camera's feed cuts off and a mysterious man laughs.",
    ],
    trivia: [
      "Larsen wears the same uniform as Collins, which caused some confusion early on in identifying the characters.",
      "The name 'Larsen' is confirmed only in the intro cutscene when Iversen screams his name. There has been confusion because Iversen and Larsen are both Norwegian, but their voices are distinct, particularly when Larsen screams and is mauled.",
      "Larsen cannot be encountered in the game normally, not even with bugs, as he only appears in a cutscene before the game starts.",
      "Though Larsen's character model is available, it is unknown if he can be spawned through mods. If he could be recruited, he would likely be assigned the Soldier or Engineer class.",
      "Coincidentally, the first victim of the Original Thing is also named Henrik Larsen.",
    ],
    gallery: [],
  },
  {
    name: "Lavelle",
    img: "./characters/Lavelle.png",
    description:
      "Lavelle is a Gen Inc researcher stationed at the Strata Medical Laboratory in Antarctica. He plays a role in the 2002 video game 'The Thing.'",
    history: [
      "Lavelle is first discovered by Blake and his team in one of the Strata Furnace rooms. Initially distrusting, he is put on Whitley's extermination list and is under threat from a Black Ops soldier intent on killing him.",
      "Blake earns Lavelle's trust and recruits him for collaboration. Together with Blake, Dixon, and Temple, Lavelle fights both the infected Thing creatures and Whitley's elite Black Ops units.",
      "At one point, they reach the Furnace Rupture, which blocks the switch needed to activate the elevator for their escape. Despite their efforts, Lavelle is killed by the explosion caused by a time bomb set by Whitley, which destroys the entire facility.",
      "Blake is the only member of the team who survives and makes it to the surface, heading towards the Transit Hangar.",
    ],
    trivia: [
      "Lavelle can succumb to the infection and transform into a Thing if exposed to attacks from infected creatures for long enough.",
      "Lavelle's fate highlights the tragic nature of the game's storyline, where several characters meet untimely deaths, often due to betrayal or the threat of assimilation by the Thing.",
    ],
    gallery: ["Lavelle-thing"],
  },
  {
    name: "North",
    img: "./characters/North.png",
    description:
      "North is a Soldier assigned to the Arctic Marines' Bravo Team, sent to investigate the U.S. Outpost 31. He appears in the 2002 video game 'The Thing.'",
    history: [
      "North was part of Bravo Team, assigned to investigate the U.S. Outpost 31 after the US Military lost contact with it. He arrived alongside fellow team members Burrows, Weldon, and Captain Blake.",
      "Upon investigating the outpost, the team discovered a UFO, an unidentified dead body, and the body of Childs. With no confirmed survivors, Colonel Whitley ordered the outpost to be destroyed with C4 charges.",
      "Bravo Team was instructed to return to base, but Blake chose to assist Alpha Team after losing contact with them at the Norwegian outpost. The others returned to base without Blake.",
    ],
    personality: [
      "North displays bravery and a no-nonsense attitude, especially when the team finds the first corpse at Outpost 31. While Weldon panics, North remains calm, urging the team to investigate the cause.",
      "Despite his confidence, North admits that the discovery of a strange UFO creeps him out, showcasing a more human side to his character.",
    ],
    quote:
      '"I\'m locked, loaded, and ready to make shit dead!" — North, to Blake.',
    gallery: [],
  },
  {
    name: "Pace",
    img: "./characters/Pace.png",
    description:
      "Pace was an American combat engineer assigned to the Arctic Marines' Alpha Team and tasked with investigating the Thule Station. He appears in the 2002 video game 'The Thing.'",
    history: [
      "Pace, along with other members of Alpha Team, was ordered to investigate the nearby Norwegian Outpost. The team discovered it was partially destroyed and seemingly deserted. During their investigation, they were attacked by several Thing creatures, resulting in heavy casualties.",
      "Pace and the team discovered a secret underground hangar, known as the Pyron Hangar. However, they lost one of their team members, Williams, in the storm.",
      "Pace was then attacked by Iversen, a Norwegian Radio Operator, and took refuge in a nearby watch tower. He mistakenly threw grenades at Blake, his own captain, thinking Blake was a hostile, only to realize the error.",
      "Pace confirmed to Blake that the rest of the team was missing. The duo continued exploring, eventually finding Williams hiding in the mess hall, unwilling to trust them. After killing three Full Walkers, Williams agreed to join the team and granted access to the Radio Room, which was unfortunately beyond repair.",
      "The team was ambushed and fought off swarms of Thing beasts, including Brute Walkers and an unknown Assimilant. After the battle, they pursued Iversen to the Pyron Hangar.",
      "Pace, like Williams, eventually succumbed to the Thing and was transformed into an Assimilant. Blake was forced to kill him and continue his investigation.",
    ],
    personality: [
      "Pace shows courage and determination, even in dire situations, like when he threw grenades at Blake, though his mistake was later scolded by his captain.",
      "He is resourceful and quick to act, yet vulnerable to the paranoia and fear caused by the Thing infection, especially after the team suffered multiple losses.",
    ],
    quote:
      '"I\'m locked, loaded, and ready to make shit dead!" — North, to Blake.',
    gallery: [
      {
        image: "Pacething",
        description:
          "The Pace-Thing, his transformed state after succumbing to the infection.",
      },
    ],
    trivia: [
      "There is an Easter egg in the game's audio files involving Pace. If you open the 'mainui.pak' file, you can hear parodies of U.S. Presidents George W. Bush, Ronald Reagan, George H.W. Bush, Bill Clinton, Arnold Schwarzenegger, and characters Pace and Pierce congratulating Blake.",
      "Unlike Williams, who can be saved from becoming an Assimilant by bypassing a certain part of the game, Pace cannot be saved, as the player is forced to progress past the point where he turns into an Assimilant.",
    ],
  },
  {
    name: "Parnevik",
    img: "./characters/Parnevik.jpg",
    description:
      "Parnevik is a Medic found onboard the Pyron Sub Facility in Antarctica in the 2002 video game 'The Thing.'",
    history: [
      "Parnevik was a Medic trapped in the testing chambers inside the Pyron Submersible Facility. He wore the same uniform as Iversen, a Norwegian Radio Operator, which suggests he may have originally been a captured Norwegian test subject from Thule Station, rather than a Gen Inc researcher.",
      "Parnevik was found to be an imitation, meaning he was assimilated by the Thing. He was quickly disposed of by Blake and his team, which may imply that he was one of the original infected members of Iversen's research group, who had been captured by Gen Inc.",
      "Price, a Gen Inc Engineer, mentions some of his people being trapped in the testing chambers, hinting that Parnevik might have once been part of Gen Inc.",
    ],
    strategy: {
      description:
        "To keep Parnevik from turning into the Thing, you must avoid bringing him further into the testing chambers. Parnevik will remain in your team as long as he is not led past the point where he was first found. To prevent him from transforming, immediately bring up the squad menu and order him to follow you. If done correctly, Parnevik will stay in your team.",
    },
    gallery: [
      {
        image: "Parnevikthing",
        description:
          "The Parnevik-Thing, his transformed state after being assimilated by the Thing.",
      },
    ],
    trivia: [
      "Parnevik will reveal himself as an imitation when encountered, similar to Stanmore, Carter (Soldier), and Guy. Like them, he does not talk.",
      "The uniform worn by Parnevik is identical to Iversen's, suggesting that he may have originally been part of the Norwegian Antarctic Research Team, rather than Gen Inc. Unlike Gen Inc medical researchers, Parnevik does not wear the white Medic uniform with a red cross and biohazard symbol.",
      "Parnevik is a surname of Swedish origin, which, combined with his uniform, further hints at him possibly being of Swedish/Norwegian descent, aligning him with Iversen's team.",
      "Parnevik and Fisk share the exact same burst-out Assimilant model. However, while both models are similar, Fisk's is more flawed, with missing neck sections and clipping. Both models also have a glitch where their heads become invisible from a distance.",
    ],
  },
  {
    name: "Peltola",
    img: "./characters/Peltola.png",
    description:
      "Peltola is a Gen Inc Engineer stationed at the Gen Inc Weapons Laboratory in Antarctica in the 2002 video game 'The Thing.'",
    history: [
      "Peltola was discovered by Blake in the Weapons Laboratory's observation room overlooking the shooting range.",
      "Peltola disappears once Blake exits the Weapons Laboratory, and the facility is destroyed. His fate is unknown, but it is most likely that he was killed during the ensuing explosions.",
    ],
    fate: "Unknown (M.I.A.) or assimilated by The Thing",
    gallery: [
      {
        image: "Peltola-thing",
        description:
          "The Peltola-Thing, his transformed state after being assimilated by The Thing.",
      },
    ],
    trivia: [
      "Peltola will become infected relatively quickly if exposed to Thing attacks.",
    ],
  },
  {
    name: "Pierce",
    img: "./characters/Pierce.png",
    description:
      "Captain Pierce is the commanding officer of the Arctic Marines' Alpha Team, tasked with investigating the Norwegian Outpost in the 2002 video game 'The Thing.'",
    history: [
      "Pierce is first encountered by Blake when he is found in a supply hut wielding a flamethrower, extremely paranoid about his team.",
      "Blake performs blood tests on the squad to calm Pierce, and Cruz is revealed as an imposter, transforming and being destroyed by Pierce's flamethrower.",
      "After the group is separated in a blizzard, Blake is briefly reunited with Pierce in the observation tower of a Norwegian research facility, but Pierce is infected.",
      "Pierce attempts to persuade Blake to kill him, but after failing, he commits suicide.",
    ],
    fate: "Commits suicide after being infected by The Thing",
    trivia: [
      "Pierce belongs to Arctic Marines Alpha Team, yet the embroidered patch on his shoulder spells Beta Team, like Blake's.",
      "Due to mission objectives, Pierce cannot be coerced at first, which is similar to Williams.",
      "In the Xbox version, no blood test is required to gain Pierce's trust. However, performing a blood test with the proper kits can help Blake earn Pierce's trust.",
      "There is an Easter egg in the game's audio files involving Pierce. Parodies of U.S. Presidents and other characters can be heard congratulating Blake after the mission.",
    ],
    gallery: [
      {
        image: "Pierce-paranoid",
        description: "Blake confronts a paranoid Pierce in The Thing (2002).",
      },
      {
        image: "Pierce-infected",
        description:
          "Blake relocates an infected Pierce after his transformation in The Thing (2002).",
      },
    ],
  },
  {
    name: "Powell",
    img: "./characters/Powell.png",
    description:
      "Powell is a Gen Inc researcher stationed at the Transit Hangar in Antarctica in the 2002 video game 'The Thing.'",
    history: [
      "Powell is found in the Transit Hangar's laboratory by Blake, where he has a brief conversation, asking Blake if he's from a 'bogus rescue team.' Blake doesn't take kindly to this, but Powell helps him afterward.",
      "Powell does not accompany Blake into the Weapons Laboratory area, and his fate remains unknown. It is assumed that he may have been assimilated by The Thing.",
    ],
    fate: "Unknown (M.I.A.) or assimilated by The Thing",
    trivia: [
      "Powell will become infected and burst out if exposed too much to Thing attacks.",
    ],
    gallery: [
      {
        image: "Powell-thing",
        description: "The Powell-Thing transformation.",
      },
    ],
  },
  {
    name: "Price",
    img: "./characters/Price.png",
    description:
      "Price is a Gen Inc researcher stationed onboard the Pyron submersible facility in Antarctica in the 2002 video game 'The Thing.'",
    history: [
      "Price is found by J.F. Blake in a small room inside the Pyron submersible facility. He informs Blake that some of his men are still trapped in the testing chambers.",
      "Price helps Blake and Faraday escape but disappears afterward. His fate is unknown, though it is assumed he was either captured by Whitley or killed offscreen.",
    ],
    fate: "Unknown (M.I.A.) or assimilated by The Thing",
    trivia: [
      "Price can become infected and burst out if attacked too much by The Thing.",
    ],
    gallery: [
      {
        image: "Pricething",
        description: "The Price-Thing transformation.",
      },
    ],
  },
  {
    name: "R.C. Whitley",
    img: "./characters/Whitley.png",
    description:
      "Colonel R.C. Whitley is a U.S. Military Colonel and Captain J.F. Blake's superior. He serves as the primary antagonist in the 2002 video game 'The Thing.' Voiced by William B. Davis.",
    history: [
      "Whitley collaborated with the bio-engineering company Gen Inc to research an extraterrestrial being known as 'The Thing' in Antarctica.",
      "He secretly established a hidden research facility to improve the development of the Cloud Virus.",
      "Whitley assigned Blake and his team to investigate the U.S. Outpost 31 and ordered it to be destroyed. He ordered Blake and Bravo Team to return to base, but Blake decided to assist Alpha Team, inadvertently becoming involved in Whitley's plot.",
      "After Blake rescued Faraday, Whitley revealed himself as the mastermind behind the operations. Blake attempted to fight back, but Whitley sedated him.",
      "Whitley offered himself as a test subject for the B4 strain of the Cloud Virus, but when Faraday disagreed, Whitley killed him.",
      "Whitley planned to use cargo planes to smuggle the Things out of Antarctica, but his plan was foiled by Blake. Whitley then set his Military Outpost to self-destruct.",
      "Blake chased Whitley through the snow field, fighting off Whitley's Black Ops unit. Whitley injected himself with the B4 strain of the virus and mutated into a massive creature.",
      "He was eventually defeated by Blake with the help of R.J. MacReady.",
    ],
    fate: "Mutated into a creature, eventually defeated by Blake with MacReady's help.",
    trivia: [
      "Whitley is voiced by William B. Davis, known for playing the Cigarette Smoking Man in 'The X-Files.'",
      "Whitley appears to desire being infected with the virus, likely due to a terminal illness, possibly cancer.",
      "In one computer journal entry, Faraday refers to Whitley as 'Commander' instead of 'Colonel.'",
      "Whitley's name is often misspelled in the game (e.g., 'Whitely').",
      "His initials 'R.C.' may be a playful reference to his belligerent nature, possibly a nod to 'arsey' or a jab at R.J. MacReady.",
      "Whitley bears some resemblance to Weyland from the 'Alien' and 'Alien vs. Predator' franchises.",
    ],
    gallery: [
      {
        image: "Whitley_recruited_dome",
        description:
          "Whitley recruited at the start of the Dome level. Note that his name is misspelled as 'Whitely.'",
      },
      {
        image: "Ghost_Whitley_bug",
        description:
          "Ghost Whitley bug, where his dead body is visible during the Dome cutscene but his usual animations are not played.",
      },
      {
        image: "Whitley_pushed_crawlspace",
        description: "Whitley pushed through the Dome crawlspace.",
      },
      {
        image: "Focused_guard",
        description:
          "A Black Ops soldier guarding a corner in the Dome. Seen only if Whitley was sniped immediately after the first cutscene.",
      },
      {
        image: "WhitCready",
        description:
          "The 'WhitCready' form, a humorous combined form of Whitley and MacReady.",
      },
      {
        image: "WhitCready_squad_menu",
        description:
          "Squad menu image of 'WhitCready,' a visual glitch combining Whitley and 'McReady.'",
      },
    ],
  },
  {
    name: "R.J. MacReady",
    img: "./characters/MacReady.png",
    role: "Helicopter Pilot",
    station: "U.S. Outpost 31",
    film_appearance: "The Thing (1982)",
    game_appearance: "The Thing (2002)",
    history: [
      "R.J. MacReady is the protagonist of the 1982 film *The Thing*, portrayed by Kurt Russell.",
      "In the 2002 video game *The Thing*, MacReady returns to assist Captain Blake in destroying a massive Thing from the air.",
      "It is not explained how MacReady survived the cold of Antarctica after the destruction of Outpost 31, nor how he managed to acquire a working helicopter three months after the events of the film.",
      "One theory is that MacReady was captured by Gen Inc and used as a test subject before escaping and stealing a helicopter to help with Blake's mission.",
    ],
    final_dialogue:
      "R.J. MacReady delivers the final lines of dialogue in the game, revealing his identity and flying off into the horizon.",
    trivia: [
      "The Chess Wizard game MacReady wrecked in the film was owned by Production Manager Robert Latham Brown. It was played on an Apple II computer, and the game was Sargon II.",
      "A scene involving MacReady and a female blow-up doll was filmed but later cut from the final film.",
      "MacReady's weapon of choice was a 12 gauge Ithaca 37 shotgun, which he used while searching the Norwegian base and during the attack by the Kennel-Thing. Later, he also used a .357 Magnum Colt Trooper Mark III revolver, given to him by Garry.",
      "MacReady's character was based on the protagonist from the novella *Who Goes There?* by John W. Campbell.",
      "In a scrapped mini-series *Return of the Thing*, it was planned that MacReady and Childs' frozen bodies would be discovered six months after the events of the 1982 film, and both would have been human.",
    ],
    gallery: [
      {
        image: "MacReadyShotgun",
        description: "R.J. MacReady wielding his 12 gauge Ithaca 37 shotgun.",
      },
      {
        image: "MacReadyHelicopter",
        description:
          "R.J. MacReady flying the helicopter in the 2002 video game.",
      },
    ],
  },
  {
    name: "Reed",
    img: "./characters/Reed.png",
    description:
      "Reed is a Gen Inc researcher and medic stationed at the Military Airstrip in Antarctica. He is discovered by Blake in the air traffic control tower.",
    history: [
      "Reed was taken captive by Whitley's Black Ops soldiers prior to Captain Blake's arrival.",
      "After being captured, two of Reed's colleagues locked themselves away in the ATC staff room for safety.",
      "He was later discovered by Blake, but his fate remains unknown as he doesn't accompany Blake to the Weapons Laboratory area.",
    ],
    fate: "Unknown (M.I.A.) or assimilated by The Thing.",
    trivia: [
      "Reed can become infected and burst out if attacked too much by The Thing.",
      "Sometimes, Reed bursts out almost immediately when attacked by the Walker that harasses him.",
    ],
    gallery: [
      {
        image: "Reed-thing",
        description:
          "The Reed-Thing, illustrating his transformation into The Thing.",
      },
    ],
  },
  {
    name: "Ryan",
    img: "./characters/Ryan.png",
    description:
      "Ryan is a Gen Inc researcher stationed at the Gen Inc Weapons Laboratory in Antarctica. He is discovered by Blake in the weapons laboratory lobby, where he and his colleague, Stolls, hold each other at gunpoint.",
    history: [
      "Ryan was discovered by Blake in the weapons laboratory lobby, where he and Stolls were holding each other at gunpoint.",
      "Ryan had allowed Cohen to fetch medical supplies, but Cohen never returned, causing concern for Stolls.",
      "With Blake's intervention, Ryan was revealed to be an imposter while Stolls was proven to be human.",
      "Journal entries indicate that Ryan was working on an 'anti-thing virus' along with Stolls and Cohen.",
      "Despite various incidents involving The Thing, Ryan is the only researcher who appears to be in good spirits, suggesting he may have been infected for quite some time.",
    ],
    fate: "Infected or assimilated by The Thing.",
    trivia: [
      "When Stolls unsuccessfully tries to go through the timed door, Ryan's reprimand is used instead of Stolls', with a softer tone and no swearing.",
      "Ryan shares a bug with Carter (Soldier), where he bursts out and remains in human form but acts like an Assimilant.",
      "If the player trusts Ryan over Stolls, he will accompany the player to the CCTV control panel but will turn on them quickly, causing mission failure.",
      "There is no cutscene in the game files for Ryan not turning, only for Stolls doing so.",
    ],
    gallery: [
      {
        image: "Ryan-thing",
        description:
          "The Ryan-Thing revealing itself, showcasing his transformation.",
      },
    ],
  },
  {
    name: "Ryder",
    img: "./characters/Ryder.png",
    description:
      "Ryder is an unused character from the 2002 video game The Thing. He was intended to appear in the Strata Medical Facility but was cut from the game during development.",
    fate: "Cut from the game, but his files remain in the game's folders.",
    history: [
      "Ryder's files can be found in the game's data folder, specifically in 'english.pak' under the 'Animations' and 'Sound' folders.",
      "He was intended to appear in a cutscene at the Strata Medical Facility, where he would provide the laser beam sequence code.",
      "Ryder's character model and voice were replaced with Fisk's during development, likely due to time constraints or design changes.",
      "The cutscene involving Ryder, which would have played with him in Carter's place, still exists in the game files, but his character was ultimately removed.",
    ],
    trivia: [
      "It is unknown why Ryder was cut from the game, but it was likely to prevent the player from easily knowing the security gate laser beam code.",
      "Ryder is one of the few known cut characters from the game, alongside Hawk and Hobson, whose files remain in the game's folders.",
      "He does not appear to have any face models or voice files in the game, unlike other cut characters like Hawk and Hobson.",
      "The dialogue in the cutscene is still present in the game files, with Ryder's voice being different from Fisk's, despite using Fisk's character model.",
    ],
    cutscene: {
      location: "Strata Medical Facility",
      dialogue: {
        blake: "I need the sequence for the security gate, do you know it?",
        ryder: "Uh, yeah, yeah, the sequence is: er, on, off, off, on.",
      },
    },
    gallery: [
      {
        image: "Ryder_Cutscene",
        description:
          "A screenshot of Ryder's cutscene, where his voice and dialogue can be heard despite using Fisk's character model.",
      },
    ],
  },
  {
    name: "Dr. Shaun Faraday",
    img: "./characters/Shaun_Faraday.png",
    description:
      "Dr. Shaun Faraday is a Medic and the Chief Medical Researcher of Gen Inc, working on the Cloud Virus and studying the extraterrestrial organism known as the Thing in the 2002 video game The Thing.",
    role: "Medic",
    fate: "Shot and killed by Whitley.",
    history: [
      "Dr. Faraday was stationed at Gen Inc's Strata Medical Laboratory research facility in Antarctica, conducting experiments on the Thing's regenerative abilities to create the B4 strain of the Cloud Virus.",
      "During the outbreak caused by Thing Beasts, Faraday became trapped at the Pyron Submersible Facility, a research facility beneath the Pyron Hangar near the Norwegian Weather Station.",
      "Blake and his team managed to rescue Faraday, but they were ambushed by Whitley and his Black Ops unit. Faraday was later involved in experiments on Blake, suggesting Blake might have developed immunity to the Thing.",
      "Faraday rejected Whitley’s request to be a test subject for the Cloud Virus due to his unstable condition, which led to Whitley shooting and killing Faraday.",
    ],
    trivia: [
      "Faraday is voiced by John Carpenter, the director of The Thing (1982), in an uncredited cameo.",
      "He serves as a Medic when recruited by the player.",
      "Faraday's name is misspelled as 'Sean' in his first journal entry, a possible oversight or typo.",
    ],
    cutscene: {
      location: "Pyron Submersible Facility",
      dialogue: {
        blake: "You've been trapped here for a while, are you okay?",
        faraday:
          "I'm... fine, but the experiments are... dangerous. But... you may have developed some immunity to the Thing after all those encounters...",
      },
    },
    gallery: [
      {
        image: "Faraday_Experiment",
        description:
          "Dr. Faraday conducting an experiment on Blake to assess his potential immunity to the Thing's infection.",
      },
    ],
  },
  {
    name: "Stanmore",
    img: "./characters/Stanmore.png",
    description:
      "Stanmore is a Gen Inc researcher and test subject held in the Strata Medical Laboratory in Antarctica. He is an imitation, posing as a human before being discovered and disposed of.",
    role: "Engineer (Test Subject)",
    fate: "Disposed of by Blake and his team after revealing himself as an imitation.",
    history: [
      "Stanmore was an Engineer held in Cell 8 of the Strata Medical Laboratory cell block, where he was being used as a test subject.",
      "When Blake and his team encounter him, they quickly discover that Stanmore is an imitation, leading to his disposal.",
      "Though initially testing negative on the blood test, Stanmore bursts out as a Thing once he attempts to leave his cell or after a set amount of time passes.",
    ],
    trivia: [
      "Stanmore reveals himself as an imitation quickly, similar to other imitations like Parnevik, Carter (Soldier), and Guy.",
      "If the blood test hypo is used quickly, Stanmore will test negative, but he will still burst out if he tries to leave his cell.",
      "Unlike other imitations, Stanmore does not talk.",
      "Stanmore trusts Blake completely from the moment he is encountered.",
      "It is difficult to get Stanmore to leave Cell 8, as he will freeze and burst out once he approaches the door. One way to get him out is to use the 'Go to' option in the squad menu and have him activate a switch, though he will burst shortly after.",
    ],
    cutscene: {
      location: "Strata Medical Laboratory, Cell 8",
      dialogue: {
        blake: "You are not one of them, are you?",
        stanmore: "(No response, pauses before bursting out as the Thing)",
      },
    },
    gallery: [
      {
        image: "Stanmore_Thing",
        description:
          "The Stanmore-Thing after bursting out, showing the terrifying transformation from imitation to full infection.",
      },
    ],
  },
  {
    name: "Stolls",
    img: "./characters/Stolls.png",
    description:
      "Stolls is a Gen Inc researcher stationed at the Gen Inc Weapons Laboratory in Antarctica, who works on an 'anti-thing virus' alongside Ryan and Cohen.",
    role: "Researcher",
    fate: "Succumbs to the infection and reveals himself as a Thing.",
    history: [
      "Stolls was working alongside Ryan and Cohen on an 'anti-thing virus' in the Weapons Laboratory.",
      "Journal entries suggest that Stolls was dedicated to the project, spending an entire night researching their 'current specimens'.",
      "He was initially discovered by Blake in the weapons laboratory lobby, where he and Ryan held each other at gunpoint, believing each other to be infected.",
      "Blake intervenes and reveals that Ryan is the imposter, while Stolls is human.",
      "Despite aiding Blake as far as the black weapons storage area, Stolls succumbs to the infection and transforms into a Thing.",
    ],
    trivia: [
      "There is a notable oversight with Stolls' infection. After unsuccessfully trying to get through the timed door, he bursts out before entering the Thing-infested zone, which is where he was supposed to get infected.",
      "Stolls may burst out before reaching the timed door, especially if Ryan has already turned into a Thing and is still nearby.",
      "When Stolls attempts to get through the timed door and fails, he chastises Blake using Ryan's voice line, which is less aggressive than Stolls' intended response, suggesting a development error. His actual response, recorded in the sound files, is much more aggressive and uses profanity.",
    ],
    cutscene: {
      location: "Gen Inc Weapons Laboratory, Timed Door Area",
      dialogue: {
        blake: "I thought you said you had this figured out.",
        stolls:
          "(After failing to get through the timed door) 'What the hell happened? I thought I made it pretty goddamn simple what you had to do! Now let's try it again, and this time, asshole, pay attention!'",
      },
    },
    gallery: [
      {
        image: "Paranoid_Stolls_and_Ryan",
        description:
          "Stolls and Ryan holding each other at gunpoint, both paranoid about the other's true nature.",
      },
      {
        image: "Stolls_Thing",
        description:
          "The Stolls-Thing, showing the grotesque transformation after he succumbs to the infection.",
      },
    ],
  },
  {
    name: "Temple",
    img: "./characters/Temple.png",
    description:
      "Temple is a Gen Inc researcher and Medic stationed at the Strata Medical Laboratory in Antarctica.",
    role: "Medic",
    fate: "Killed in the explosion caused by the time bomb set by Whitley, leaving his final fate ambiguous.",
    history: [
      "Temple was found injured in an office in the Strata Furnace during the initial outbreak of the Thing within the Strata Medical Laboratory.",
      "Blake arrives and heals Temple with a Health Pack, earning his trust.",
      "Temple had been placed on Whitley's extermination list prior to meeting Blake, and an attempt had been made on his life.",
      "Alongside Blake, Dixon, and Lavelle, Temple fought through both the Thing Beasts and Whitley's elite Black Ops units.",
      "The team encountered the Furnace Rupture, blocking access to the switch needed to operate the elevator, and Temple was killed by the explosion caused by the time bomb set by Whitley, destroying the entire facility.",
    ],
    trivia: [
      "Temple can succumb to the infection and burst out if attacked too much by The Thing.",
      "It is possible to position Temple to enter the boss fight with the Furnace Rupture by making him follow Blake closely, but this can be difficult as Lavelle or Dixon might be positioned instead.",
      "During the explosion cutscene, Temple's location varies depending on where he is positioned. In the Xbox version, he may be seen either just outside the elevator, far enough to survive, or inside the elevator with Blake, potentially surviving the explosion, though he does not appear in the next level.",
    ],
    cutscene: {
      location: "Strata Medical Laboratory, Furnace Rupture",
      dialogue: {
        temple:
          "Why do Dixon and Lavelle think they can survive a massive explosion?",
        blake: "(Blake silently salutes their bravery)",
      },
    },
    gallery: [
      {
        image: "Temple_Thing",
        description:
          "The Temple-Thing, showing Temple after being infected and transformed.",
      },
      {
        image: "Temple_Furnace_Rupture",
        description:
          "Temple positioned in various locations during the explosion cutscene, hinting at his uncertain fate.",
      },
    ],
  },
  {
    name: "Unnamed Medic",
    img: "./characters/Unnamedmedic.png",
    description:
      "The Unnamed Medic (known as 'NPCEntity_I' in the squad menu) is a Gen Inc Soldier and researcher, presumably with a medical background, stationed at the Pyron Sub Facility.",
    role: "Soldier/Medic",
    fate: "Killed by a Walker in the hydraulic override room before Blake could intervene.",
    history: [
      "The Unnamed Medic was wounded in the hydraulic override room and overpowered by a Walker, ultimately being killed before Blake could save him.",
      "Blake witnesses his death via a CCTV monitor in the facility's operations room.",
      "Though referred to as the Unnamed Medic, the character is actually a Soldier, which is only known through cheats or examining the squad menu.",
      "He carries a pistol and has high trust in the player when first met, but cannot heal the player because he is classified as a Soldier, not a Medic.",
      "The Unnamed Medic's voice files were never used in-game, and he's referred to as an NPCEntity in the squad menu.",
    ],
    trivia: [
      "The Unnamed Medic is identified as 'NPCEntity_I' in the squad menu and was never intended to be accessible by the player.",
      "Despite wearing a Medic's outfit, he is a Soldier and does not have the ability to heal the player.",
      "He is not an Imitation, as he passes the Blood Test and never turns into The Thing.",
      "The Unnamed Medic can only be reached if cheats (like immortal NPCs cheat) are activated, and even then, he will still die if the player is too slow.",
      "If saved, he behaves like a normal NPC and will follow the player briefly, attacking Things if given a weapon. However, he doesn't speak.",
      "He won't follow the player past certain areas and must be pushed or prompted to move, especially through maze-like corridors.",
    ],
    cutscene: {
      location: "Pyron Sub Facility, Hydraulic Override Room",
      dialogue: {
        unnamed_medic: "No dialogue, as he has no voice files.",
      },
    },
    gallery: [
      {
        image: "Unnamedmedicpreplab",
        description:
          "The Unnamed Medic in the Prep Lab, at the end of the level.",
      },
      {
        image: "Unnamedmedic",
        description:
          "The Unnamed Medic in full view, showing his appearance as a Soldier with a Medic's outfit.",
      },
      {
        image: "NPCEntity_I",
        description:
          "The Unnamed Medic listed as 'NPCEntity_I' in the squad menu, indicating he was not intended to be a playable character.",
      },
    ],
  },
  {
    name: "Weldon",
    img: "./characters/Weldon.png",
    role: "Medic",
    fate: "Unspecified, as he does not appear to survive long enough in the game to have a clear fate.",
    history: [
      "Weldon was assigned to the Arctic Marines' Bravo Team to investigate U.S. Outpost 31 after the US Military lost contact with the base for several days.",
      "Along with fellow team members North, Burrows, and Captain Blake, Weldon discovered a UFO and an unidentified dead body at the outpost, as well as the body of Childs.",
      "With no confirmed survivors, Colonel Whitley ordered the outpost to be destroyed by planting C4 charges around it, and Bravo Team was ordered to return to base.",
      "Blake insisted on assisting Alpha Team after losing contact with them at the Norwegian outpost, but after Blake was dropped off, the rest of the team returned to base.",
    ],
    personality: [
      "As a medic, Weldon exhibits a great amount of fear, particularly at the sight of the first corpse and the UFO. He is terrified of the situations he finds himself in.",
      "He wets himself upon seeing the UFO and struggles to maintain composure in the face of danger, showing panic.",
      "Despite his fear, Weldon remains loyal to Bravo Team, vowing to heal his teammates as soon as possible, stating that he would not be 'carrying any dead bodies back.'",
    ],
    voice_actor: "Cam Clarke (uncredited role)",
    gallery: [
      {
        image: "Weldon1",
        description: "Weldon in the game, showcasing his medic outfit.",
      },
    ],
    trivia: [
      "Weldon is voiced by Cam Clarke, famous for his role as Liquid Snake in the Metal Gear series, though this role is uncredited.",
    ],
  },
  {
    name: "Whitley's Black Ops",
    img: "./characters/Black_Ops_Soldiers.png",
    type: "Covert U.S. Special Forces unit",
    history: [
      "The Black Ops unit assisted Colonel R.C. Whitley in rescuing Dr. Shaun Faraday, the Chief Medical Researcher of Gen Inc, from the Pyron Sub Facility.",
      "After rescuing Faraday and capturing Captain Blake, the Black Ops soldiers were tasked by the infected Whitley to serve as the security force of Gen Inc's Strata Medical Laboratory and the nearby Military Outpost.",
      "Blake and his team fought through hundreds of Black Ops soldiers to eventually kill the mutated Whitley with the help of helicopter pilot, R.J. MacReady.",
    ],
    equipment: [
      "Black Ops soldiers are equipped with military-grade body armor and gas masks.",
      "They wield weapons available to the player, such as Pistols, Shotguns, Machine Guns, Sniper Rifles, Flamethrowers, and Grenade Launchers.",
    ],
    trivia: [
      "It is possible to disarm and kill Black Ops soldiers using the Stun Gun and Stun Grenades.",
      "In the Strata Medical Laboratory, there is a special immortal variant that emerges from the security elevator if Blake pushes the wrong switches. One of these soldiers even carries a Grenade Launcher.",
    ],
    gallery: [
      {
        image: "BlackOpsIncinerator",
        description: "Black Ops Incinerator in action.",
      },
      {
        image: "BlackOpsSoldier1",
        description: "Black Ops soldier suited up and ready for action.",
      },
      {
        image: "BlackOpsSoldiers1",
        description: "A group of Black Ops soldiers on the move.",
      },
    ],
  },
  {
    name: "Williams",
    img: "./characters/Williams.png",
    role: "Medic",
    team: "Arctic Marines' Alpha Team",
    history: [
      "Williams, along with Alpha Team, was tasked with investigating the Norwegian Outpost, which was found partially destroyed and deserted.",
      "The team encountered several Thing Beasts during their investigation, leading to heavy casualties.",
      "Williams got separated in the storm but eventually barricaded himself in the mess hall. After encountering Blake and Pace, he initially mistrusted them but later joined the team.",
      "Williams and the team discovered a ruined radio, and after fighting off Thing Beasts, they pursued Iversen, who had stolen the radio and locked himself in the Pyron Hangar.",
      "Williams eventually succumbed to the Thing and transformed into an Assimilant, which Blake had to kill before continuing his investigation.",
    ],
    strategy_to_keep_alive: [
      "A design oversight allows players to keep Williams alive through the Norwegian Weather Station level by bypassing the building where he is scripted to turn into an Assimilant.",
      "By using flares, blowtorches, or flamethrowers to blow up a locked door outside the storage building, players can avoid the building where Williams would otherwise transform.",
      "Players must be cautious as Williams can panic at the sight of corpses and may shoot indiscriminately, so he needs to be disarmed, pushed out of fearful areas, or given an adrenaline shot to prevent him from attacking the player.",
    ],
    gallery: [
      {
        image: "WilliamsThing",
        description: "The Williams-Thing after transformation.",
      },
    ],
    trivia: [
      "Due to mission objectives, Williams cannot be coerced into following Blake until certain conditions are met.",
      "Despite being kept alive until the end of the Norwegian Weather Station level, Williams will not follow Blake to the Pyron Hangar and will disappear after the level ends.",
    ],
  },
  {
    name: "Pilot",
    role: "Pilot",
    team: "Arctic Marines' Alpha Team",
    history: ["Pilot of Alpha Team, brings the Alpha Team to U.S Outpost 31."],
    strategy_to_keep_alive: [],
    gallery: [],
    trivia: [],
  },
];
