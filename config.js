const SOCIETES = {
  cep: {
    id: 'cep',
    nom: 'Compagnie d\'Electricite Parisienne',
    couleurPrimaire: '#1a365d',
    couleurSecondaire: '#2c5282',
    emailCompta: 'compta@cep75.fr',
    techniciens: ['Christophe Tavares', 'Ricardo Dassilva', 'Mathieu Rodriguez'],
    adresse: '6, rue de Metz, 94240 L\'Hay-les-Roses',
    telephone: '01 56 04 19 96',
    email: 'contact@cep75.fr',
    siteWeb: 'www.cep75.fr',
    materiel: [
      { categorie: 'Cables', produits: [
        { nom: '3G0,75', prix: 0.6, unite: 'm', reference: '' },
        { nom: '3G1,5', prix: 1.3, unite: 'm', reference: '' },
        { nom: '3G2,5', prix: 2, unite: 'm', reference: '' },
        { nom: '5G1,5', prix: 2.1, unite: 'm', reference: '' },
        { nom: '5G2,5', prix: 3.2, unite: 'm', reference: '' },
        { nom: '5G6', prix: 4.5, unite: 'm', reference: '' },
        { nom: '5G10', prix: 14, unite: 'm', reference: '' },
        { nom: '5G16', prix: 22, unite: 'm', reference: '' },
        { nom: '4X35', prix: 50, unite: 'm', reference: '' },
        { nom: '3G1,5 Pyrolion', prix: 3, unite: 'm', reference: '' },
        { nom: '3G2,5 Pyrolion', prix: 4.35, unite: 'm', reference: '' },
        { nom: '5G2,5 Pyrolion', prix: 6.5, unite: 'm', reference: '' },
        { nom: 'Cable Info Cat.6', prix: 1.8, unite: 'm', reference: '' },
        { nom: 'Cable Sono 2X1,5', prix: 3.4, unite: 'm', reference: '' },
        { nom: 'Gaine Grise D20', prix: 1, unite: 'm', reference: '' }
      ]},
      { categorie: 'Disjoncteurs Mono', produits: [
        { nom: '2A Mono 6kA', prix: 37, unite: 'u', reference: 'A9P22602' },
        { nom: '4A Mono 6kA', prix: 39, unite: 'u', reference: 'A9P22604' },
        { nom: '10A Mono 6kA', prix: 34, unite: 'u', reference: 'A9P22610' },
        { nom: '16A Mono 6kA', prix: 34, unite: 'u', reference: 'A9P22616' },
        { nom: '20A Mono 6kA', prix: 34, unite: 'u', reference: 'A9P22620' },
        { nom: '32A Mono 6kA', prix: 37, unite: 'u', reference: 'A9P22632' }
      ]},
      { categorie: 'Disjoncteurs Tetra', produits: [
        { nom: '10A Tetra 6kA', prix: 114, unite: 'u', reference: 'A9P22710' },
        { nom: '16A Tetra 6kA', prix: 114, unite: 'u', reference: 'A9P22716' },
        { nom: '20A Tetra 6kA', prix: 114, unite: 'u', reference: 'A9P22720' },
        { nom: '32A Tetra 6kA', prix: 130, unite: 'u', reference: 'A9P22732' },
        { nom: '40A Tetra 6kA', prix: 158, unite: 'u', reference: 'A9P22740' },
        { nom: '63A Tetra 10kA', prix: 275, unite: 'u', reference: 'A9P24463' }
      ]},
      { categorie: 'Appareillages Plexo', produits: [
        { nom: 'Inter. Plexo Saillie', prix: 15, unite: 'u', reference: '069711L' },
        { nom: 'Prise Plexo Simple', prix: 22, unite: 'u', reference: '069731L' },
        { nom: 'Prise Plexo Double', prix: 42, unite: 'u', reference: '069768L' },
        { nom: 'Prise Plexo Triple', prix: 86, unite: 'u', reference: '069680L' },
        { nom: 'Prise Tetra 20A', prix: 72, unite: 'u', reference: '091657' },
        { nom: 'Fiche Tetra 20A', prix: 25, unite: 'u', reference: '055637' },
        { nom: 'Boite Plexo D60', prix: 8, unite: 'u', reference: '092003' },
        { nom: 'Boite Plexo D80', prix: 12, unite: 'u', reference: '092013' },
        { nom: 'Boite Plexo D100', prix: 27, unite: 'u', reference: '092020' },
        { nom: 'Prise Encastre Simple', prix: 30, unite: 'u', reference: '069831L' },
        { nom: 'Prise Encastre Double', prix: 59, unite: 'u', reference: '069562L' },
        { nom: 'Prise Encastre Triple', prix: 90, unite: 'u', reference: '080053' },
        { nom: 'Prise Tetra Encastre', prix: 67, unite: 'u', reference: '080051' }
      ]},
      { categorie: 'BAES & Peignes', produits: [
        { nom: 'BAES Legrand', prix: 130, unite: 'u', reference: '062525' },
        { nom: 'BAES URA ONE', prix: 120, unite: 'u', reference: '111013V' },
        { nom: 'Telecommande BAES', prix: 290, unite: 'u', reference: '062520' },
        { nom: 'Peigne Mono DT40', prix: 42, unite: 'u', reference: 'A9XPN624' },
        { nom: 'Peigne Tetra IDT40', prix: 76, unite: 'u', reference: 'A9XPP724' },
        { nom: 'Peigne Tetra IC60', prix: 28, unite: 'u', reference: 'R9PXH424' }
      ]},
      { categorie: 'Eclairage & LED', produits: [
        { nom: 'Ampoule E27 2W', prix: 8, unite: 'u', reference: '716630' },
        { nom: 'Ampoule E27 4W Dim', prix: 9, unite: 'u', reference: '165458' },
        { nom: 'Guirlande 12m', prix: 125, unite: 'u', reference: '' },
        { nom: 'Ampoule GU10 7W', prix: 9, unite: 'u', reference: '' },
        { nom: 'Douille GU10', prix: 1.1, unite: 'u', reference: '' },
        { nom: 'Ruban LED COB480', prix: 28, unite: 'm', reference: '' },
        { nom: 'Profile Alu', prix: 7.6, unite: 'm', reference: '' },
        { nom: 'Capot Blanc', prix: 7.2, unite: 'm', reference: '' },
        { nom: 'Transfo 24V 100W', prix: 105, unite: 'u', reference: '' }
      ]},
      { categorie: 'Variateurs', produits: [
        { nom: 'RVLED 250W', prix: 390, unite: 'u', reference: '' },
        { nom: 'RVLED 500W', prix: 430, unite: 'u', reference: '' },
        { nom: 'RVLED 1000W', prix: 490, unite: 'u', reference: '' },
        { nom: 'Potentiometre', prix: 65, unite: 'u', reference: '1977' },
        { nom: 'Support Potentiometre', prix: 8.5, unite: 'u', reference: 'A9A15152' }
      ]}
    ]
  },
  elechosystem: {
    id: 'elechosystem',
    nom: 'Elecho System SARL',
    couleurPrimaire: '#E85D04',
    couleurSecondaire: '#C54E03',
    emailCompta: 'compta@elechosystem.com',
    techniciens: ['Will Lussaud', 'Aurelien Mathieu', 'Frederick Pagau'],
    adresse: '6, rue de Metz, 94240 L\'Hay-les-Roses',
    telephone: '01 56 04 19 96',
    email: 'contact@elechosystem.com',
    siteWeb: 'www.elechosystem.com',
    materiel: [
      { categorie: 'Cables Courant Faible', produits: [
      ]},
      { categorie: 'Sonorisation', produits: [
      ]},
      { categorie: 'Alarme', produits: [
      ]},
      { categorie: 'Videosurveillance', produits: [
      ]},
      { categorie: 'TV & Multimedia', produits: [
      ]}
    ]
  }
};
