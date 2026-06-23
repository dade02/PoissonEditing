## coordinate frames
- definisco un punto
- trasformo un punto( e di conseguenza anche un oggetto)

### trasformazione
funzione T(p) -> p'.

esempio
- spostamento dell' oggetto
- rotazione 
- scaling

tutto ciò si può scrivere in un modo molto elegante.\
Le trasformazioni che studiamo sono la classe delle trasformazioni affini.

__trasformazioni lineari__\
Prendiamo trasformazioni lineari: scrivibili come prodotto tra una matrice e le coordinate di un punto.\
Mp = p'

__spostamento__\
se prendo il punto p che è l' origine e lo moltiplico per M, mi viene sempre fuori 0. Quindi con la trasformazione lineare non posso rappresentare la traslazione dell' oggetto.

Allora facciamo Mp + t = p'. Questa classe di trasformazioni si chiama __trasformazioni affini__ (più utilizzata in computer grafica)

A = [M t] altro modo di scriverla, significa prima colonne di M e poi colonna t.\
Ap = Mp + t


se sposto un oggetto senza cambiare la forma, significa che prendo tutti i punti di quell' oggetto e gli aggiungo un vettore.\
A_traslazione = p + V\
dunque M = I e t = v

                 1 0 0 tx
Atraslazione = [ 0 1 0 ty ]  = [I t]
                 0 0 1 tz

devo definire il punto che è il centro della trasformazione.


__scaling__\
Ascaling = s*p

s > 1 : ingrandire
s < 1 : rimpicciolire

t = 0\
mi serve una matrice che quando la moltiplico per p mi viene fuori sp\
        s 0 0
M = [   0 s 0   ]
        0 0 s

Ascaling = [ dag(S) 0 ]

A_non_uniform_scaling = [ s0 0 0 ]
                          0 s1 0
                          0  0 s2

se voglio fare mirroring su un determinato asse, inverto il segno di quella s e lascio gli altri uguali. se voglio riflessione rispetto all' origine, inverto tutte le s.

__rotazione__\
la rotazione è definito da un angolo e dal centro di un' origine.\
voglio scrivere p' rispetto a p.

p [px 0]\
p' [p'x p'y]

se o_ è l' angolo di rotazione, allora p' = [ px cos o_, px sin o_]

q' = [  qx sin o_, qx cos o_]

dunque la matrice di rotazione è M2 = [  cos o_ -sin o_
                                        sin o_ cos o_ ]

la rotazione rispetto l' asse z posso riscriverla come cos o_ -sin o_ 0
                                                       sin o_ cos 0_ 0
                                                         0      0    1

dunque riesco a scrivere trasformazioni che mi danno rotazione rispetto gli assi, scaling, traslazione. Queste trasformazioni sono equivalenti a un cambiamento di sistema di coordinate.

Ap = Mp + t,   M = [m1 m2 m3 ] , Ap = m1p1 + m2p2 +m3p3 + t

prendiamo sistema di coordinate con 3 assi e1, e2, e3 di lunghezza 1 e ortogonali tra loro.

ei * ej = Dy

se ho un punto, le coordinate di questo punto sono le proiezioni sugli assi.\
p0, p1 e p2 sono lunghezze delle proiezioni.

Af = [ e1 e2 e3 o]

le colonne sono linearmente indipendenti, matrice ortonormale.


per tornare indietro, dato un punto nel sistema di coordinate, come faccio a calcolare p1, p2 e p3.\
la lunghezza pi = (p - 0 ) * ei

visto che M * v = sum_i ( col Mi*vi) 

p' = Mp -> p = M^-1 (p' - o)

__visto che è ortonormale, M^-1 = Mtrasposta__

---
## combinazione di trasformazioni
A1 * (A2 * p) = A1 * (M2p+ t2) = M1M2p + M1t2 + t1 
                                 ---M--- ----t----
( A1 * A2) = [M1M2 M1t2+ t1]

il prodotto tra matrici non è commutativo.

se voglio trasformare rispetto all' origine, applico una trasformazione che mi trasla all' origine, poi trasformo e poi traslo nuovamente al punto iniziale.\
se voglio trasformare rispetto ad un asse, prima allineo all' asse che voglio l' asse di input.

Av = A (p2-p1) = Ap2 -Ap1 = Mp2+t - Mp1 -t = Mp2-Mp1 = M(p2-p1) = Mv

dunque possiamo immaginare trasformazioni come matrici o come origini e assi.

