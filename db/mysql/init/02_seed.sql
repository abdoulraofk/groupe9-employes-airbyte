USE rh_source;

INSERT INTO services (code, nom) VALUES
  ('DSI',  'Direction des Systemes d''Information'),
  ('RH',   'Ressources Humaines'),
  ('FIN',  'Finances et Comptabilite'),
  ('COM',  'Commercial et Marketing'),
  ('LOG',  'Logistique et Achats');

INSERT INTO fonctions (code, libelle) VALUES
  ('DEV',  'Developpeur'),
  ('ADM',  'Administrateur systeme'),
  ('CHEF', 'Chef de service'),
  ('ASS',  'Assistant administratif'),
  ('CPT',  'Comptable'),
  ('COMM', 'Charge commercial');

INSERT INTO employes (matricule, nom, prenom, email, service_id, fonction_id, date_embauche, actif) VALUES
  ('EMP0001','KABORE','Awa','awa.kabore@rh-demo.bf',1,1,'2021-03-01',1),
  ('EMP0002','OUEDRAOGO','Boukary','boukary.ouedraogo@rh-demo.bf',1,2,'2019-09-15',1),
  ('EMP0003','SAWADOGO','Fatimata','fatimata.sawadogo@rh-demo.bf',1,3,'2017-01-10',1),
  ('EMP0004','ZONGO','Issouf','issouf.zongo@rh-demo.bf',1,1,'2022-06-20',1),
  ('EMP0005','KONE','Mariam','mariam.kone@rh-demo.bf',1,4,'2023-02-01',1),
  ('EMP0006','TRAORE','Seydou','seydou.traore@rh-demo.bf',2,3,'2016-04-11',1),
  ('EMP0007','NIKIEMA','Aminata','aminata.nikiema@rh-demo.bf',2,4,'2020-11-03',1),
  ('EMP0008','COMPAORE','Hamidou','hamidou.compaore@rh-demo.bf',2,4,'2021-08-18',1),
  ('EMP0009','YAMEOGO','Salimata','salimata.yameogo@rh-demo.bf',2,2,'2018-05-25',0),
  ('EMP0010','BATIONO','Rasmane','rasmane.bationo@rh-demo.bf',3,3,'2015-10-01',1),
  ('EMP0011','SANOU','Alizeta','alizeta.sanou@rh-demo.bf',3,5,'2019-01-14',1),
  ('EMP0012','OUATTARA','Drissa','drissa.ouattara@rh-demo.bf',3,5,'2022-09-09',1),
  ('EMP0013','DIALLO','Kadiatou','kadiatou.diallo@rh-demo.bf',3,5,'2023-07-01',1),
  ('EMP0014','SANKARA','Paul','paul.sankara@rh-demo.bf',3,4,'2020-02-17',1),
  ('EMP0015','KABRE','Edwige','edwige.kabre@rh-demo.bf',4,3,'2017-03-22',1),
  ('EMP0016','ZOUNGRANA','Moussa','moussa.zoungrana@rh-demo.bf',4,6,'2021-05-05',1),
  ('EMP0017','BARRY','Nassira','nassira.barry@rh-demo.bf',4,6,'2022-01-19',1),
  ('EMP0018','OUEDRAOGO','Karim','karim.ouedraogo@rh-demo.bf',4,6,'2023-04-12',1),
  ('EMP0019','GUIRE','Lassina','lassina.guire@rh-demo.bf',4,4,'2018-12-02',0),
  ('EMP0020','KINDA','Rachelle','rachelle.kinda@rh-demo.bf',5,3,'2016-06-30',1),
  ('EMP0021','SOME','Bassirou','bassirou.some@rh-demo.bf',5,1,'2020-08-08',1),
  ('EMP0022','ILBOUDO','Fanta','fanta.ilboudo@rh-demo.bf',5,4,'2021-10-21',1),
  ('EMP0023','TAPSOBA','Yacouba','yacouba.tapsoba@rh-demo.bf',5,4,'2022-11-11',1),
  ('EMP0024','KABORE','Noellie','noellie.kabore@rh-demo.bf',1,1,'2024-01-08',1),
  ('EMP0025','DABIRE','Clement','clement.dabire@rh-demo.bf',2,1,'2024-03-15',1),
  ('EMP0026','ROUAMBA','Suzanne','suzanne.rouamba@rh-demo.bf',3,2,'2019-07-07',1),
  ('EMP0027','KIEMTORE','Jean','jean.kiemtore@rh-demo.bf',4,2,'2017-09-29',1),
  ('EMP0028','NANA','Aicha','aicha.nana@rh-demo.bf',5,2,'2023-10-02',1),
  ('EMP0029','KERE','Wendkouni','wendkouni.kere@rh-demo.bf',1,3,'2015-02-23',1),
  ('EMP0030','SAWADOGO','Ibrahim','ibrahim.sawadogo@rh-demo.bf',2,1,'2024-06-01',1);
