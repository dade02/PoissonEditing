# Riassunto Dettagliato: Poisson Image Editing

Questo documento fornisce un riassunto capitolo per capitolo del celebre articolo scientifico **"Poisson Image Editing"** di Patrick Pérez, Michel Gangnet e Andrew Blake (Microsoft Research UK, SIGGRAPH 2003).

---

## 1. Introduzione (Introduction)

### Contesto e Obiettivo
L'editing di immagini si divide solitamente in modifiche globali (come la correzione del colore o del contrasto) e modifiche locali (confinate a una specifica selezione dell'immagine). Gli strumenti classici per inserire una porzione di immagine sorgente in un'immagine di destinazione (come il copia-incolla o il "clonaggio" tradizionale) generano spesso giunture visibili (boarders/seams) a causa delle differenze di colore ed esposizione. Il tentativo di sfumare i bordi ("feathering") maschera solo parzialmente il problema.

### La Soluzione Proposta
Gli autori propongono una tecnica basata sulla risoluzione di **equazioni differenziali parziali (PDE) di Poisson con condizioni al contorno di Dirichlet**. Questa formulazione matematica permette di:
1. Interpolare in modo continuo i valori della destinazione verso l'interno dell'area selezionata.
2. Mantenere intatti i dettagli spaziali (il gradiente) dell'immagine sorgente.

### Motivazioni Scientifiche
La scelta del modello si basa su due osservazioni fondamentali:
1. **Percezione visiva**: Il sistema visivo umano è molto sensibile alle variazioni brusche (corrispondenti al Laplaciano) e tende ad ignorare le variazioni di intensità lente e graduali (i gradienti a bassa frequenza).
2. **Unicità della soluzione**: Una funzione scalare definita su un dominio limitato è determinata univocamente dai suoi valori al contorno (condizioni di Dirichlet) e dal suo Laplaciano all'interno. La risoluzione dell'equazione di Poisson garantisce quindi una soluzione unica.

### Lavoro Correlato (Related Work)
* **Fattal et al. (2002)**: Utilizzava l'equazione di Poisson per la compressione della gamma dinamica (HDR) applicandola a tutta l'immagine con condizioni al contorno di Neumann. Poisson Image Editing estende questo approccio a selezioni arbitrarie con condizioni di Dirichlet.
* **Elder & Goldberg (2001)**: Proponevano l'editing nel dominio dei contorni (edgels), ma richiedeva specifiche complesse e portava a perdite di dettagli.
* **Burt & Adelson (1983) - Multiresolution Blending**: La fusione basata su piramidi Laplaciane mescola pixel distanti a bassa risoluzione, introducendo a volte effetti di "ghosting" o mescolamento a lungo raggio indesiderati. La tecnica di Poisson evita questo problema operando localmente in modo esatto.

---

## 2. Formulazione Matematica ed Equazione di Poisson (Poisson solution to guided interpolation)

### Il Modello Continuo
Sia $S$ il dominio dell'immagine e $\Omega$ una regione chiusa con bordo $\partial\Omega$.
* $f^*$ è la funzione nota dell'immagine di destinazione (fuori da $\Omega$).
* $f$ è la funzione incognita da ricostruire all'interno di $\Omega$.
* $\mathbf{v}$ è il **campo vettoriale di guida** (guidance vector field) definito su $\Omega$.

Il problema viene formulato come una minimizzazione di energia $L_2$:
$$\min_{f} \iint_{\Omega} |\nabla f - \mathbf{v}|^2 \quad \text{con } f|_{\partial\Omega} = f^*|_{\partial\Omega}$$

La soluzione a questo problema variazionale deve soddisfare l'associata equazione di Eulero-Lagrange, che è proprio l'**equazione di Poisson con condizioni al contorno di Dirichlet**:
$$\Delta f = \text{div } \mathbf{v} \quad \text{su } \Omega, \quad \text{con } f|_{\partial\Omega} = f^*|_{\partial\Omega}$$

Dove $\nabla$ è l'operatore gradiente e $\Delta$ è il Laplaciano ($\Delta = \frac{\partial^2}{\partial x^2} + \frac{\partial^2}{\partial y^2}$), mentre $\text{div } \mathbf{v}$ è la divergenza del campo di guida.
Se il campo vettoriale $\mathbf{v}$ è conservativo (cioè è il gradiente di un'immagine sorgente $g$, $\mathbf{v} = \nabla g$), si può definire la correzione additiva $\tilde{f} = f - g$. Questa soddisfa l'equazione di Laplace:
$$\Delta \tilde{f} = 0 \quad \text{su } \Omega, \quad \text{con } \tilde{f}|_{\partial\Omega} = (f^* - g)|_{\partial\Omega}$$
Ciò significa che la correzione applicata all'interno di $\Omega$ è una membrana elastica che interpola linearmente la differenza (errore) tra la sorgente e la destinazione lungo il contorno $\partial\Omega$.

### Risolutore Discreto (Discrete Poisson Solver)
Per immagini digitali composte da griglie di pixel, il problema continuo viene discretizzato.
Sia $p$ un pixel all'interno di $\Omega$, e $N_p$ l'insieme dei suoi vicini 4-connessi. La minimizzazione discreta diventa:
$$\min_{f|_\Omega} \sum_{\langle p,q \rangle \cap \Omega \neq \emptyset} (f_p - f_q - v_{pq})^2 \quad \text{con } f_p = f^*_p \text{ per } p \in \partial\Omega$$
dove $v_{pq}$ è la proiezione del campo di guida sul segmento orientato da $p$ a $q$. Nel caso $\mathbf{v} = \nabla g$, si ha $v_{pq} = g_p - g_q$.

Derivando rispetto a ciascun valore incognito $f_p$, si ottiene un sistema di equazioni lineari simultanee:
$$\forall p \in \Omega, \quad |N_p| f_p - \sum_{q \in N_p \cap \Omega} f_q = \sum_{q \in N_p \cap \partial\Omega} f^*_q + \sum_{q \in N_p} v_{pq}$$

Questo sistema è sparso, simmetrico e definito positivo. A causa delle forme arbitrarie del contorno $\partial\Omega$, viene risolto tramite metodi iterativi come:
* Iterazione di **Gauss-Seidel** con sovrarilassamento (SOR).
* Metodo **Multigrid** (V-cycle), ideale per aree molto grandi o per implementazioni su GPU.

---

## 3. Clonazione Trasparente (Seamless Cloning)

### Importazione di Gradienti (Importing Gradients)
La scelta fondamentale consiste nel prendere come campo guida direttamente il gradiente di un'immagine sorgente $g$:
$$\mathbf{v} = \nabla g \implies \Delta f = \Delta g \quad \text{su } \Omega, \quad \text{con } f|_{\partial\Omega} = f^*|_{\partial\Omega}$$
* **Concealment (Nascondimento)**: Copiare una porzione di sfondo pulito sopra un oggetto indesiderato. Il sistema compensa le variazioni di luce del contorno, nascondendo l'oggetto.
* **Insertion (Inserimento)**: Inserire oggetti con contorni complessi (come capelli o rami di alberi) in un nuovo sfondo senza bisogno di un ritaglio preciso (è sufficiente una selezione molto grossolana con il lazo).
* **Trasferimento Monocromatico**: Se il colore della sorgente stona con la destinazione, si può convertire la sorgente in scala di grigi prima dell'inserimento, trasferendo solo la texture (pattern di intensità).

### Miscelazione di Gradienti (Mixing Gradients)
Nei casi in cui si debbano sovrapporre oggetti semitrasparenti o con buchi (es. scritte, arcobaleni) su sfondi strutturati, l'importazione diretta dei soli gradienti sorgente distruggerebbe la texture di sfondo. 
Per ovviare a questo, viene definito un campo guida ibrido che seleziona punto per punto il gradiente di intensità maggiore tra sorgente e destinazione:
$$\forall x \in \Omega, \quad \mathbf{v}(x) = \begin{cases} \nabla f^*(x) & \text{se } |\nabla f^*(x)| > |\nabla g(x)| \\ \nabla g(x) & \text{altrimenti} \end{cases}$$
Questo metodo preserva i dettagli salienti di entrambe le immagini, consentendo ad esempio la fusione perfetta di scritte o di un arcobaleno trasparente. Evita inoltre l'effetto di "sanguinamento" (bleeding) del colore dello sfondo se un oggetto nella destinazione tocca il contorno della selezione.

---

## 4. Editing delle Selezioni (Selection Editing)

Invece di usare un'immagine sorgente esterna $g$, si possono implementare trasformazioni locali modificando il gradiente dell'immagine originale $f^*$ stessa all'interno della regione $\Omega$:

### Appiattimento delle Texture (Texture Flattening)
Passando il gradiente $\nabla f^*$ attraverso un filtro che mantiene solo le caratteristiche principali (i contorni salienti rilevati da un edge detector $M$) e azzera il resto:
$$\mathbf{v}(x) = M(x) \nabla f^*(x)$$
Il risultato è un effetto di "appiattimento" in cui la texture interna dell'oggetto viene rimossa o levigata (eliminando i piccoli dettagli e il rumore), mentre la struttura principale e i bordi rimangono nitidi.

### Modifiche Locali dell'Illuminazione (Local Illumination Changes)
Applica una trasformazione non lineare al gradiente dell'immagine nel dominio logaritmico per comprimere i gradienti forti e amplificare quelli deboli:
$$\mathbf{v} = \alpha^\beta |\nabla f^*|^{-\beta} \nabla f^*$$
Questo permette di illuminare oggetti in ombra (sottoesposti) o ridurre i riflessi speculari indesiderati in modo estremamente naturale, mantenendo la coerenza visiva con i bordi della selezione.

### Modifiche Locali del Colore (Local Color Changes)
Permette di cambiare il colore di un oggetto selezionato grossolanamente senza alterarne la texture.
* **Decolorazione dello sfondo**: Si imposta la sorgente $g$ pari all'immagine a colori e la destinazione $f^*$ pari alla sua luminanza (scala di grigi).
* **Ricolorazione di oggetti**: Si moltiplicano i canali RGB della sorgente $g$ per determinati fattori di scala prima di risolvere il sistema.

### Generazione di Texture Piastrellabili (Seamless Tiling)
Per rendere un'immagine rettangolare ripetibile all'infinito (tileable) senza giunture visibili:
1. Si impostano condizioni al contorno periodiche Dirichlet (i bordi opposti della selezione rettangolare vengono forzati ad avere gli stessi valori, es. la media tra i valori del bordo nord e del bordo sud).
2. Si risolve l'equazione di Poisson usando il gradiente originale dell'immagine come guida.

---

## 5. Conclusione (Conclusion)

Gli autori concludono che il framework di interpolazione guidata basato sulle equazioni di Poisson offre uno strumento estremamente versatile e potente. La caratteristica chiave che distingue questo metodo dalle tecniche tradizionali è **l'assenza di necessità di una selezione accurata dei contorni**. Una selezione laza e approssimativa è sufficiente perché l'equazione di Poisson adatta automaticamente il contenuto al contesto di destinazione in modo Seamless. 

Inoltre, il documento accenna alla possibilità di combinare le tecniche (es. clonare un oggetto e contemporaneamente appiattirne la texture) e suggerisce sviluppi futuri come il controllo della nitidezza per modificare artificialmente la messa a fuoco (focus).
