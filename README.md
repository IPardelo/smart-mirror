# Smart-Mirror
Espello con raspberry que pode mostrar o tempo, as novas e a hora.

## Instalación
## Code

> Si xa tes [git](https://git-scm.com/book/en/v2/Getting-Started-Installing-Git) instalado, clona o repositorio.

```
git clone https://github.com/IPardelo/smart-mirror.git
```

## Instalar as dependencias

> Si xa tes [pip](https://pip.pypa.io/en/stable/installing/) instalado...

```
sudo pip install -r requirements.txt
```

```
sudo apt-get install python-imaging-tk
```

## Running

Para executar o programa usa:
```
python smartmirror.py
```

## Liñas obligatorias que substituír

* **Liña 20**: trocamos pola nosa IP Pública.
* **Liña 25**: trocamos polo noso API TOKEN.
* **Liña 28**: trocamos NONE pola nosa latitude. ***p.ex.** ‘43.3455975’*
* **Liña 29**: trocamos NONE pola nosa lonxitude. ***p.ex.** ‘-8.4567084’*

## Liñas opcionais que substituír

* **Liña 30**: valor de tamaño da temperatura.  
* **Liña 31**: valor de tamaño do reloxo.  
* **Liña 32**: valor de tamaño do título “Novas”.  
* **Liña 33**: valor de tamaño da data, previsión do tempo e novas.  
* **Liña 216**: trocamos “News” por “Novas”.  

## Vídeo e instruccións
[![video](assets/readme.png)](https://youtu.be/fkVBAcvbrjU)